"""Vouchers and coupons. Measured: wallet listing and cart apply; DELETE is inferred."""

from collections.abc import Sequence

from ..types import JsonObject, as_list, as_object
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
        """Raw wallet payload: `vouchers`, `benefitsToken`, `limit`, `total`.

        The token rotates per call; use it right before `apply_to_cart`.
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
    ) -> Sequence[JsonObject]:
        """Vouchers from `wallet`, ready to filter with `available_for`."""
        vouchers = self.wallet(
            latitude=latitude,
            longitude=longitude,
            distance_km=distance_km,
            merchant_id=merchant_id,
        ).get("vouchers", [])
        return [as_object(item) for item in vouchers] if isinstance(vouchers, list) else []

    @staticmethod
    def available_for(vouchers: Sequence[JsonObject], merchant_id: str) -> Sequence[JsonObject]:
        """Keep `AVAILABLE` vouchers not restricted to another merchant."""
        out: list[JsonObject] = []
        for voucher in vouchers:
            if voucher.get("status") != "AVAILABLE":
                continue
            campaign = as_object(voucher.get("campaign") or {})
            conditions = [as_object(c) for c in as_list(campaign.get("conditions") or [])]
            merchant_only = [
                as_list(c.get("value") or []) for c in conditions if c.get("type") == "MERCHANT"
            ]
            if merchant_only and merchant_id not in (merchant_only[0] or []):
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
        """Apply one voucher; returns the signed cart with the discount applied.

        `token` is a fresh `benefitsToken` from `wallet`. Pass `code=` (typed
        coupon) or `campaign_id=` (wallet voucher), never both.
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
        """DELETE on the same route; never observed on the wire."""
        self._t.request("DELETE", endpoints.CART_VOUCHER.format(cart_id=cart_id))
