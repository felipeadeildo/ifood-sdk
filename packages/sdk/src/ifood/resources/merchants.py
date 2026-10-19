"""Merchant lookups. Detail lives on the marketplace host and needs no auth."""

from ..models import Merchant
from ..types import JsonObject, as_object
from ..wire import endpoints
from ..wire.config import MARKETPLACE
from ..wire.transport import Transport


class Merchants:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def get(self, merchant_id: str, *, channel: str = "IFOOD") -> Merchant:
        payload = self._t.get(
            endpoints.MERCHANT_DETAIL.format(merchant_id=merchant_id),
            params={"channel": channel},
            absolute_url=MARKETPLACE + endpoints.MERCHANT_DETAIL.format(merchant_id=merchant_id),
        )
        return Merchant.model_validate(payload)

    def catalog(self, merchant_id: str, *, latitude: float, longitude: float) -> JsonObject:
        """Menu. PerimeterX-gated: works only with a browser-originated session."""
        return as_object(
            self._t.get(
                endpoints.MERCHANT_CATALOG.format(merchant_id=merchant_id),
                params={"latitude": latitude, "longitude": longitude},
            )
        )
