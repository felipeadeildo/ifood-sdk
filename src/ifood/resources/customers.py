"""Account: profile and saved addresses."""

from typing import Any

from ..models import Address, Profile
from ..types import as_list
from ..wire import endpoints
from ..wire.transport import Transport


class Customers:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def profile(self) -> Profile:
        return Profile.model_validate(self._t.get(endpoints.CUSTOMER_ME))

    def add_address(self, address: dict[str, Any]) -> Address:
        """Save a new address.

        The body carries `city`, `state`, `country`, `streetName`, `streetNumber`,
        `neighborhood`, `coordinates` and `postalCode`, exactly as the web client sends.
        """
        payload = self._t.post(endpoints.CUSTOMER_ADDRESSES, json_body=address)
        return Address.model_validate(payload)

    def addresses(self) -> list[Address]:
        payload = self._t.get(endpoints.CUSTOMER_ADDRESSES)
        return [Address.model_validate(item) for item in as_list(payload)]
