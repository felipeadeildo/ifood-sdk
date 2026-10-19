"""Address search and reverse geocoding.

Lives on the logistics host and takes the address application key, not the user token.
"""

from typing import Any

from ..types import JsonObject, as_list, as_object
from ..wire import endpoints
from ..wire.config import DEFAULT_PROFILE, LOGISTICS
from ..wire.transport import Transport


class Locations:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def search(self, query: str) -> list[JsonObject]:
        """Turn a typed address into candidate places with coordinates."""
        result = self._t.get(
            endpoints.GEOCODE,
            params={"query": query},
            absolute_url=LOGISTICS + endpoints.GEOCODE,
            extra_headers={
                "x-application-key": DEFAULT_PROFILE.address_application_key.value,
                "platform": "webapp",
            },
        )
        return [as_object(item) for item in as_list(as_object(result).get("addresses", []))]

    def reverse(self, latitude: float, longitude: float) -> dict[str, Any]:
        return as_object(
            self._t.get(
                endpoints.REVERSE_GEOCODE,
                params={"latitude": latitude, "longitude": longitude},
                absolute_url=LOGISTICS + endpoints.REVERSE_GEOCODE,
                extra_headers={"x-application-key": DEFAULT_PROFILE.address_application_key.value},
            )
        )
