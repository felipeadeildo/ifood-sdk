"""Session state: bearer tokens plus the edge cookies that keep the BFF answering."""

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

EDGE_COOKIES = ("cf_clearance", "__cf_bm", "_px3", "_pxhd", "_pxvid", "pxcts")
COOKIE_OWNERS = {
    "cf_clearance": "cloudflare",
    "__cf_bm": "cloudflare",
    "_px3": "perimeterx",
    "_pxhd": "perimeterx",
    "_pxvid": "perimeterx",
    "pxcts": "perimeterx",
}
CHECKOUT_COOKIE_PREFIX = "x-ifood-device-payment-"


@dataclass(slots=True)
class Session:
    access_token: str | None = None
    refresh_token: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    expires: dict[str, int] = field(default_factory=dict)
    user_id: str | None = None

    @property
    def has_user(self) -> bool:
        return bool(self.access_token)

    @property
    def is_complete(self) -> bool:
        """A usable user session needs both tokens: refresh is what survives a deploy."""
        return bool(self.access_token and self.refresh_token)

    @property
    def device_id(self) -> str | None:
        return self.cookies.get("aDeviceId")

    def expires_in(self) -> int | None:
        """Seconds until the JWT expires, decoded locally so no call is spent."""
        claims = self._claims()
        if claims is None:
            return None
        expiry = claims.get("exp")
        return None if not isinstance(expiry, int) else int(expiry - time.time())

    def checkout_secret(self) -> str | None:
        """Device payment credential. Sent as a header; never logged."""
        for name, value in self.cookies.items():
            if name.startswith(CHECKOUT_COOKIE_PREFIX):
                return value
        return None

    def edge_status(self) -> dict[str, bool]:
        return {name: name in self.cookies for name in EDGE_COOKIES}

    def describe(self) -> list[dict[str, object]]:
        """Per edge cookie: owner, presence and seconds left. Observation, not contract."""
        now = int(time.time())
        owners = {
            "cf_clearance": "cloudflare",
            "__cf_bm": "cloudflare",
            "_px3": "perimeterx",
            "_pxhd": "perimeterx",
            "_pxvid": "perimeterx",
            "pxcts": "perimeterx",
        }
        out: list[dict[str, object]] = []
        for name in EDGE_COOKIES:
            remaining = None
            if (expiry := self.expires.get(name)) is not None:
                remaining = max(0, expiry - now)
            out.append(
                {
                    "name": name,
                    "owner": owners.get(name, "unknown"),
                    "present": name in self.cookies,
                    "seconds_left": remaining,
                }
            )
        return out

    def _claims(self) -> dict[str, object] | None:
        if not self.access_token or self.access_token.count(".") != 2:
            return None
        segment = self.access_token.split(".")[1]
        segment += "=" * (-len(segment) % 4)
        try:
            return json.loads(base64.urlsafe_b64decode(segment))
        except ValueError:
            return None

    @classmethod
    def from_jar(cls, path: str | Path) -> Session:
        cookies: dict[str, str] = {}
        expires: dict[str, int] = {}
        for line in Path(path).read_text().splitlines():
            if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
                continue
            parts = line.removeprefix("#HttpOnly_").split("\t")
            if len(parts) >= 7:
                cookies[parts[5]] = parts[6]
                expires[parts[5]] = int(parts[4] or 0)
        return cls(
            expires=expires,
            access_token=cookies.get("aAccessToken"),
            refresh_token=cookies.get("aRefreshToken"),
            cookies=cookies,
            user_id=cookies.get("x-ifood-user-id"),
        )

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "user_id": self.user_id,
                    "cookies": self.cookies,
                    "expires": self.expires,
                },
                indent=1,
            )
        )
        target.chmod(0o600)


def _remaining(expiry: int | None, now: int) -> int | None:
    return None if expiry is None else max(0, expiry - now)
