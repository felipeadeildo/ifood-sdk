"""Cart and checkout.

Writes are frozen at the edge: Cloudflare returns a challenge for POST/PUT from any
client whose TLS is not the browser that minted the session. Reads are unaffected.
"""

import json
from collections.abc import Callable, Sequence

from ..models import Address, CartResponse, CheckoutResult, Merchant
from ..types import JsonObject
from ..wire import endpoints
from ..wire.transport import Transport
from .cart_build import (
    Account,
    CartDraft,
    CartItem,
    CartPayloadError,
    CartVersion,
    build_payload,
    draft_from,
)


class Carts:
    """Cart writes. `build` is pure; the other methods perform the calls."""

    def __init__(self, transport: Transport, account: Callable[[], Account] | None = None) -> None:
        self._t = transport
        self._account = account

    def build(
        self,
        draft: CartDraft | None = None,
        version: CartVersion = "v2",
        merchant: Merchant | JsonObject | str | None = None,
        address: Address | JsonObject | None = None,
        items: Sequence[CartItem | JsonObject] | None = None,
        account: Account | JsonObject | None = None,
        merchant_id: str | None = None,
        merchant_name: str | None = None,
        delivery_id: str = "DEFAULT",
        now: bool = True,
        delivery_by: str = "IFOOD",
    ) -> JsonObject:
        """Build and validate a cart body without touching the network.

        Accepts our objects or raw dicts, and fills in what the session already knows:

            client.carts.build(
                merchant=client.merchants.get(id),
                address=client.customers.addresses()[0],
                items=[CartItem("item", 1, SubItem("option"))],
            )

        `account` comes from the session unless given.
        """
        if draft is not None:
            return build_payload(draft, version)

        resolved_account = account if account is not None else self._session_account()
        draft = draft_from(
            merchant=merchant,
            address=address,
            items=items,
            account=resolved_account,
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            delivery_id=delivery_id,
            now=now,
            delivery_by=delivery_by,
        )
        return build_payload(draft, version)

    def _session_account(self) -> Account | JsonObject | None:
        return self._account() if self._account is not None else None

    def create(self, payload: JsonObject) -> CartResponse:
        """`payload` must carry merchant, address, items (with `subItems`), delivery,
        account and source. See `docs/cart.md` for the shape measured on the wire."""
        return CartResponse.model_validate(self._t.post(endpoints.CART_CREATE, json_body=payload))

    def set_payment_method(self, cart_id: str, payload: JsonObject) -> CartResponse:
        return CartResponse.model_validate(
            self._t.request(
                "PUT", endpoints.CART_PAYMENT_METHOD.format(cart_id=cart_id), json_body=payload
            )
        )

    def apply_voucher(self, cart_id: str, payload: JsonObject) -> CartResponse:
        return CartResponse.model_validate(
            self._t.request(
                "PUT", endpoints.CART_VOUCHER.format(cart_id=cart_id), json_body=payload
            )
        )

    def remove_voucher(self, cart_id: str) -> None:
        self._t.request("DELETE", endpoints.CART_VOUCHER.format(cart_id=cart_id))

    def checkout(self, cart_id: str, payload: JsonObject) -> CheckoutResult:
        """Finalises the order. `payload["cartRequest"]` is a JSON *string*, not an object.

        Raises `ValueError` on a dict because that mistake only shows up as a 400 later.
        """
        if isinstance(payload.get("cartRequest"), dict):
            raise ValueError("cartRequest must be a JSON string, not an object")
        if "cartRequest" not in payload:
            raise ValueError("cartRequest is required")
        if "signature" not in payload:
            raw = payload["cartRequest"]
            if not isinstance(raw, str):
                raise ValueError("cartRequest must be a JSON string")
            inner = json.loads(raw)
            if isinstance(inner, dict) and isinstance(inner.get("signature"), str):
                payload["signature"] = inner["signature"]
        return CheckoutResult.model_validate(
            self._t.post(endpoints.CART_CHECKOUT.format(cart_id=cart_id), json_body=payload)
        )


__all__ = ["CartDraft", "CartPayloadError", "Carts", "build_payload"]
