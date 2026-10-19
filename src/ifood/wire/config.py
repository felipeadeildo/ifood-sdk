"""Wire constants with provenance.

None of this is a secret: it all ships in the public web bundle. Keeping `source` on
each constant means a stale value can be traced instead of guessed.
"""

from dataclasses import dataclass, field
from typing import Literal

Rotation = Literal["deploy", "service", "stable"]


@dataclass(frozen=True, slots=True)
class WireConstant:
    name: str
    value: str
    source: str
    rotation: Rotation = "deploy"


BFF = "https://www.ifood.com.br/site-api"
MARKETPLACE = "https://marketplace.ifood.com.br"
LOGISTICS = "https://logistics-api.ifood.com.br"
PAYMENT = "https://payment.ifood.com.br"


@dataclass(frozen=True, slots=True)
class WireProfile:
    """Headers the BFF expects. Identity routes reject the body if any of these is missing."""

    app_name: WireConstant = field(
        default=WireConstant("app_name", "consumer_webapp", "bundle config", "stable")
    )
    app_version: WireConstant = field(
        default=WireConstant("app_version", "9.178.5", "package.json inside _app chunk", "deploy")
    )
    country: WireConstant = field(
        default=WireConstant("country", "BR", "captured request", "stable")
    )
    platform: WireConstant = field(
        default=WireConstant("platform", "Desktop", "captured request", "stable")
    )
    client_application_key: WireConstant = field(
        default=WireConstant(
            "x-client-application-key",
            "41a266ee-51b7-4c37-9e9d-5cd331f280d5",
            "FASTER_APP_KEY in bundle config",
            "service",
        )
    )
    address_application_key: WireConstant = field(
        default=WireConstant(
            "x-application-key",
            "Zw@W#GbKp@UyXMYcBTsZFavt3",
            "ADDRESS_X_APPLICATION_KEY in bundle config",
            "service",
        )
    )
    device_model: WireConstant = field(
        default=WireConstant("x-device-model", "Linux Chrome", "captured request", "stable")
    )
    user_agent: WireConstant = field(
        default=WireConstant(
            "user-agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/155.0.0.0 Safari/537.36",
            "browser that minted the edge cookies",
            "deploy",
        )
    )

    def headers(self) -> dict[str, str]:
        return {
            "app_name": self.app_name.value,
            "app_version": self.app_version.value,
            "country": self.country.value,
            "platform": self.platform.value,
            "x-client-application-key": self.client_application_key.value,
            "x-device-model": self.device_model.value,
            "user-agent": self.user_agent.value,
            "accept": "application/json, text/plain, */*",
            "accept-language": "pt-BR,pt;q=1",
        }


DEFAULT_PROFILE = WireProfile()


def profile_from_session(session: object, base: WireProfile | None = None) -> WireProfile:
    """Overrides that the session itself carries.

    The jar ships `aAppVersion` and `aFasterAppKey`, so a deploy rotation is absorbed
    without editing code. Values fall back to the pinned constants when missing.
    """
    profile = base or DEFAULT_PROFILE
    cookies = getattr(session, "cookies", {})
    version = cookies.get("aAppVersion")
    key = cookies.get("aFasterAppKey")
    return WireProfile(
        app_version=WireConstant(
            "app_version",
            version or profile.app_version.value,
            "cookie aAppVersion" if version else profile.app_version.source,
            "deploy",
        ),
        client_application_key=WireConstant(
            "x-client-application-key",
            key or profile.client_application_key.value,
            "cookie aFasterAppKey" if key else profile.client_application_key.source,
            "service",
        ),
        user_agent=profile.user_agent,
    )
