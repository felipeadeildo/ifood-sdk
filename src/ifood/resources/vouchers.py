"""Vouchers and coupons.

Both routes are measured against the live web app:

- `GET /site-api/v3/customers/me/wallet/benefits` lists the wallet and returns a
  `benefitsToken` that rotates per call.
- `PUT /site-api/v2/carts/{cart_id}/voucher` applies one voucher, carrying that
  `benefitsToken` plus either the voucher `code` (manual coupon) or the
  `campaignId` (wallet voucher). The 200 body is the signed cart response with
  the discount applied.

`remove_from_cart` (`DELETE`) has no captured request yet: the shape below is
inferred and must be probed before being relied on.
"""

from collections.abc import Sequence

from ..types import JsonObject, as_object
from ..wire import endpoints
from ..wire.transport import Transport


class Vouchers:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def wallet(
        self,
        *,
        latitude: float,
        longitude: float,
        distance_km: float = 10.0,
        merchant_id: str | None = None,
    ) -> JsonObject:
        """The raw wallet payload: `vouchers`, `benefitsToken`, `limit`, `total`.

        The token rotates per call, so this is the one to use right before
        `apply_to_cart`. Each voucher carries `code`, `status`,
        `campaign.conditions` and `campaign.effects`. `merchant_id` is passed
        through, but captured bodies with and without it were identical; filter
        locally with `available_for` when in doubt.
        """
        params: dict[str, str | float] = {
            "lat": latitude,
            "lon": longitude,
            "distanceInKm": distance_km,
        }
        if merchant_id is not None:
            params["merchantId"] = merchant_id
        return as_object(self._t.get(endpoints.WALLET_BENEFITS, params=params))

    def list(
        self,
        *,
        latitude: float,
        longitude: float,
        distance_km: float = 10.0,
        merchant_id: str | None = None,
    ) -> list[JsonObject]:
        """The vouchers from `wallet`, ready to filter with `available_for`."""
        vouchers = self.wallet(
            latitude=latitude,
            longitude=longitude,
            distance_km=distance_km,
            merchant_id=merchant_id,
        ).get("vouchers", [])
        return [as_object(item) for item in vouchers] if isinstance(vouchers, list) else []

    @staticmethod
    def available_for(vouchers: Sequence[JsonObject], merchant_id: str) -> list[JsonObject]:
        """Local filter by the `MERCHANT` condition and `AVAILABLE` status."""
        out = []
        for voucher in vouchers:
            if voucher.get("status") != "AVAILABLE":
                continue
            campaign = voucher.get("campaign") or {}
            conditions = campaign.get("conditions") or []
            allowed = [
                condition.get("value")
                for condition in conditions
                if condition.get("type") == "MERCHANT"
            ]
            if allowed and merchant_id not in (allowed[0] or []):
                continue
            out.append(voucher)
        return out

    def apply_to_cart(
        self,
        cart_id: str,
        *,
        token: str,
        code: str | None = None,
        campaign_id: str | None = None,
    ) -> JsonObject:
        """Apply a voucher to the cart.

        `token` is the `benefitsToken` from a recent `list()` call; it rotates,
        so list and apply must happen close together. Give `code` for a manual
        coupon or `campaign_id` for a wallet voucher. Returns the signed cart
        response with the discount applied.
        """
        if (code is None) == (campaign_id is None):
            raise ValueError("exactly one of code= or campaign_id= is required")
        payload: JsonObject = {"token": token}
        if code is not None:
            payload["code"] = code
        else:
            payload["campaignId"] = campaign_id
        return as_object(
            self._t.request(
                "PUT", endpoints.CART_VOUCHER.format(cart_id=cart_id), json_body=payload
            )
        )

    def remove_from_cart(self, cart_id: str) -> None:
        self._t.request("DELETE", endpoints.CART_VOUCHER.format(cart_id=cart_id))
