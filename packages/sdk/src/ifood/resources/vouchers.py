"""Vouchers and coupons.

Only the cart-level apply/remove routes are known (from the web bundle, never seen on
the wire). Listing is an open question: no captured request exists, so this module
refuses to invent one.
"""

from collections.abc import Sequence

from ..types import JsonObject, as_object
from ..wire import endpoints
from ..wire.transport import Transport


class Vouchers:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def apply_to_cart(self, cart_id: str, payload: JsonObject) -> JsonObject:
        """`payload` carries the voucher campaign code. Unverified on the wire."""
        return as_object(
            self._t.request(
                "PUT", endpoints.CART_VOUCHER.format(cart_id=cart_id), json_body=payload
            )
        )

    def remove_from_cart(self, cart_id: str) -> None:
        self._t.request("DELETE", endpoints.CART_VOUCHER.format(cart_id=cart_id))

    def list(self) -> Sequence[JsonObject]:
        raise NotImplementedError(
            "voucher listing endpoint is not measured; capture a wallet request first"
        )
