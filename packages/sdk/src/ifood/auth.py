"""Passwordless OTP login. The only flow that needs no browser at all.

Password login does not exist on the web client: the account is identified and then a
one-time code arrives by WhatsApp, SMS or e-mail.
"""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from .errors import IfoodError
from .types import as_object, as_text
from .wire import endpoints
from .wire.session import Session
from .wire.transport import Transport


class OtpSent(BaseModel):
    key: str
    timeout_in_seconds: int = Field(default=60, alias="timeout_in_seconds")


class OtpTokens(BaseModel):
    access_token: str


class Authentication(BaseModel):
    authenticated: bool
    account_id: str | None = Field(default=None, alias="account_id")
    access_token: str
    refresh_token: str | None = Field(default=None, alias="refresh_token")


Channel = Literal["WHATSAPP", "SMS", "EMAIL"]


@dataclass(slots=True, frozen=True)
class Phone:
    """A phone number in the shape the API wants, built from whatever the caller has."""

    country_code: int
    area_code: str
    number: str

    PATTERN = re.compile(
        r"^\s*(?:\+?55[\s.-]*)?\(?\s*(?P<area>\d{2})\s*\)?[\s.-]*"
        r"(?P<first>\d{4,5})[\s.-]*(?P<last>\d{4})\s*$"
    )

    @classmethod
    def parse(cls, value: str | Phone) -> Phone:
        """Read a Brazilian phone in whatever shape the caller has it.

        Accepts `+55 11 90000-0000`, `(11) 90000-0000`, `11 90000-0000` and
        `5582900000000`. A leading zero and a missing country code are ignored.
        """
        if isinstance(value, Phone):
            return value
        match = cls.PATTERN.match(value)
        if match is None:
            raise ValueError(f"not a phone number: {value!r}")
        return cls(55, match["area"], match["first"] + match["last"])


@dataclass(slots=True)
class OtpChallenge:
    """State between "code sent" and "code verified". Expires in 60 s and is single use."""

    key: str
    timeout_seconds: int
    transport: Transport
    identifier: dict[str, object]
    challenge_token: str | None = None

    def verify(self, code: str) -> Session:
        """Exchange the code, then confirm the challenge and keep the tokens."""
        token = self._exchange(code)
        self.challenge_token = token
        self.transport.post(endpoints.OTP_CHALLENGE, json_body={"token": token, "tenant": "IFO"})
        data = Authentication.model_validate(
            self.transport.post(endpoints.OTP_AUTHENTICATION, json_body=self._authentication(token))
        )
        self.transport.session.access_token = data.access_token
        self.transport.session.refresh_token = data.refresh_token
        self.transport.session.user_id = data.account_id
        return self.transport.session

    def _authentication(self, token: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "tenant_id": "IFO",
            "token": token,
            "device_id": self.transport.session.device_id,
            **self.identifier,
        }
        if "email" not in payload:
            raise IfoodError("the last step needs the account e-mail, even for phone OTP")
        return payload

    def _exchange(self, code: str) -> str:
        tokens = OtpTokens.model_validate(
            self.transport.post(
                endpoints.OTP_ACCESS_TOKEN, json_body={"key": self.key, "auth_code": code}
            )
        )
        return tokens.access_token


class Auth:
    """Passwordless login. The account is identified, then a code arrives by WhatsApp."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def providers(self) -> list[str]:
        data = self._transport.post(endpoints.IDENTITY_PROVIDERS, json_body={"tenant_id": "IFO"})
        if not isinstance(data, list):
            raise IfoodError("providers: expected a list")
        names: list[str] = []
        for item in data:
            if isinstance(item, dict):
                names.append(as_text(as_object(item)["name"], "name"))
        return names

    def start_otp(
        self,
        phone: str | Phone,
        *,
        email: str | None = None,
        channel: Channel = "WHATSAPP",
    ) -> OtpChallenge:
        phone = Phone.parse(phone)
        body: dict[str, object] = {
            "tenant_id": "IFO",
            "type": channel,
            "phone": {
                "country_code": phone.country_code,
                "area_code": phone.area_code,
                "number": phone.number,
            },
        }
        sent = OtpSent.model_validate(
            self._transport.post(endpoints.OTP_AUTHORIZATION_CODE, json_body=body)
        )
        identifier: dict[str, object] = {"phone": body["phone"]}
        if email is not None:
            identifier["email"] = email
        return OtpChallenge(
            key=sent.key,
            timeout_seconds=sent.timeout_in_seconds,
            transport=self._transport,
            identifier=identifier,
        )
