"""HTTP transport.

One place knows about headers, cookies, the single edge retry and error mapping.
"""

import json
from collections.abc import Mapping

import httpx

from ..errors import EdgeBlocked, IfoodError, from_response
from ..types import Json
from ..wire.config import BFF, DEFAULT_PROFILE, WireProfile
from ..wire.session import Session

EDGE_RETRIES = 1
PX_COOKIES = ("_px3", "_pxhd", "_pxvid", "pxcts")


class Transport:
    """Speaks the iFood BFF dialect over httpx."""

    def __init__(
        self,
        session: Session,
        *,
        profile: WireProfile | None = None,
        base_url: str = BFF,
        timeout: float = 30.0,
    ) -> None:
        self.session = session
        self.profile = profile or DEFAULT_PROFILE
        self._client = httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=False)
        self._cookie_snapshot: tuple[tuple[str, str], ...] = ()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Transport:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def headers(self) -> dict[str, str]:
        headers = self.profile.headers()
        headers.update(self._identity_headers())
        if secret := self.session.checkout_secret():
            headers["x-ifood-device-payment-secret"] = secret
        if edge := self._edge_header():
            headers["x-px-cookies"] = edge
        return headers

    def _sync_cookies(self) -> None:
        """Keep the client jar in step with the session, and only when it changed."""
        snapshot = tuple(self.session.cookies.items())
        if snapshot == self._cookie_snapshot:
            return
        self._client.cookies.clear()
        for name, value in self.session.cookies.items():
            self._client.cookies.set(name, value)
        self._cookie_snapshot = snapshot

    def _identity_headers(self) -> dict[str, str]:
        session = self.session
        headers: dict[str, str] = {}
        if session.access_token:
            headers["authorization"] = f"Bearer {session.access_token}"
        if session.user_id:
            headers["x-ifood-user-id"] = session.user_id
        if session.device_id:
            headers["x-ifood-device-id"] = session.device_id
            headers["x-ifood-session-id"] = session.cookies.get("aSessionId", "")
        return headers

    def _edge_header(self) -> str:
        pairs = [
            f"{name}={self.session.cookies[name]}"
            for name in PX_COOKIES
            if name in self.session.cookies
        ]
        return "; ".join(pairs) + ", true" if pairs else ""

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        params: Mapping[str, str | int | float | bool] | None = None,
        absolute_url: str | None = None,
    ) -> Json:
        self._sync_cookies()
        for attempt in range(EDGE_RETRIES + 1):
            response = self._client.request(
                method,
                absolute_url or path,
                headers=self.headers(),
                json=json_body,
                params=params,
            )
            if response.status_code < 400:
                return _decode(response)
            error = self._error(response)
            if isinstance(error, EdgeBlocked) and attempt < EDGE_RETRIES:
                continue
            raise error
        raise IfoodError("unreachable")  # pragma: no cover

    def _error(self, response: httpx.Response) -> IfoodError:
        content_type = response.headers.get("content-type", "")
        body: Json = response.text if "json" not in content_type else _as_json(response)
        return from_response(response.status_code, body, dict(response.headers))

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
        absolute_url: str | None = None,
    ) -> Json:
        return self.request("GET", path, params=params, absolute_url=absolute_url)

    def post(self, path: str, *, json_body: object) -> Json:
        return self.request("POST", path, json_body=json_body)


def _as_json(response: httpx.Response) -> Json:
    try:
        return response.json()
    except json.JSONDecodeError, ValueError:
        return response.text[:500]


def _decode(response: httpx.Response) -> Json:
    if "json" not in response.headers.get("content-type", ""):
        raise IfoodError(f"expected JSON, got {response.headers.get('content-type', 'nothing')}")
    return _as_json(response)
