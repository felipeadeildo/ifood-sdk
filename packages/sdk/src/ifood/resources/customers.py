"""Account: profile and saved addresses."""

from ..models import Address, Profile
from ..types import as_list
from ..wire import endpoints
from ..wire.transport import Transport


class Customers:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def profile(self) -> Profile:
        return Profile.model_validate(self._t.get(endpoints.CUSTOMER_ME))

    def addresses(self) -> list[Address]:
        payload = self._t.get(endpoints.CUSTOMER_ADDRESSES)
        return [Address.model_validate(item) for item in as_list(payload)]
