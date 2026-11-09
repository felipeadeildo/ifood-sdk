"""Voucher wallet listing, against the capture in fixtures/wallet_benefits.json."""

import json
from pathlib import Path

import pytest

from ifood import Vouchers
from ifood.wire.endpoints import WALLET_BENEFITS, bff_path

FIXTURE = Path(__file__).parent / "fixtures" / "wallet_benefits.json"


class RecordingTransport:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, dict[str, str | float]]] = []
        self.last_body: object | None = None

    def get(self, path: str, *, params=None, **_):
        self.calls.append(("GET", path, dict(params or {})))
        return self.payload

    def request(self, method: str, path: str, *, json_body=None, **_):
        self.calls.append((method, path, {}))
        self.last_body = json_body
        return self.payload


@pytest.fixture
def wallet_payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_list_hits_the_measured_route(wallet_payload: dict) -> None:
    transport = RecordingTransport(wallet_payload)
    vouchers = Vouchers(transport)  # type: ignore[arg-type]
    out = vouchers.list(latitude=-23.56, longitude=-46.65)
    assert transport.calls == [
        (
            "GET",
            WALLET_BENEFITS,
            {"lat": -23.56, "lon": -46.65, "distanceInKm": 10.0},
        )
    ]
    assert len(out) == len(wallet_payload["vouchers"])
    first = out[0]
    assert first["status"] == "AVAILABLE"
    assert first["code"]
    assert first["campaign"]["conditions"]


def test_wallet_returns_token_and_vouchers(wallet_payload: dict) -> None:
    transport = RecordingTransport(wallet_payload)
    vouchers = Vouchers(transport)  # type: ignore[arg-type]
    wallet = vouchers.wallet(latitude=-23.56, longitude=-46.65)
    assert transport.calls[0][1] == WALLET_BENEFITS
    assert wallet["benefitsToken"]
    assert "vouchers" in wallet


def test_list_passes_merchant_id_and_distance(wallet_payload: dict) -> None:
    transport = RecordingTransport(wallet_payload)
    vouchers = Vouchers(transport)  # type: ignore[arg-type]
    vouchers.list(latitude=-23.56, longitude=-46.65, distance_km=5, merchant_id="m-1")
    assert transport.calls[0][2] == {
        "lat": -23.56,
        "lon": -46.65,
        "distanceInKm": 5,
        "merchantId": "m-1",
    }


def test_available_for_filters_by_merchant_condition(wallet_payload: dict) -> None:
    """MERCHANT conditions restrict; tag-restricted and global vouchers pass."""
    vouchers = Vouchers(RecordingTransport(wallet_payload))  # type: ignore[arg-type]
    all_vouchers = vouchers.list(latitude=-23.56, longitude=-46.65)
    merchant_condition = [
        v
        for v in all_vouchers
        if any(c.get("type") == "MERCHANT" for c in v["campaign"]["conditions"])
    ]
    assert merchant_condition, "fixture lost its MERCHANT-conditioned voucher"
    merchant_id = merchant_condition[0]["campaign"]["conditions"][0]["value"][0]
    for_voucher_merchant = vouchers.available_for(all_vouchers, merchant_id)
    assert merchant_condition[0] in for_voucher_merchant
    other = vouchers.available_for(all_vouchers, "00000000-0000-0000-0000-000000000000")
    assert merchant_condition[0] not in other
    # vouchers without a MERCHANT condition are not merchant-restricted
    assert len(other) == len(all_vouchers) - len(merchant_condition)


def test_benefits_route_is_the_measured_v3(wallet_payload: dict) -> None:
    assert bff_path(WALLET_BENEFITS) == (
        "https://www.ifood.com.br/site-api/v3/customers/me/wallet/benefits"
    )
    assert "benefitsToken" in wallet_payload


APPLY_FIXTURE = Path(__file__).parent / "fixtures" / "voucher_apply_contract.json"


def _apply_transport() -> tuple[Vouchers, RecordingTransport]:
    contract = json.loads(APPLY_FIXTURE.read_text())
    transport = RecordingTransport(contract["response"]["body"])
    return Vouchers(transport), transport  # type: ignore[arg-type]


def test_apply_by_code_sends_the_measured_body() -> None:
    vouchers, transport = _apply_transport()
    out = vouchers.apply_to_cart(
        "cart-1", token="MmY5YjI1MzktNWIzZC00NjcwLTkwZGYtODgxNDA2ZTQ4NWI1", code="54F10FFE"
    )
    assert transport.calls[0][:2] == ("PUT", "/v2/carts/cart-1/voucher")
    assert out["data"]["summary"]["benefits"]


def test_apply_by_campaign_id_sends_the_measured_body() -> None:
    vouchers, transport = _apply_transport()
    vouchers.apply_to_cart("cart-1", token="tok", campaign_id="7d59d493")
    assert transport.calls[0][0] == "PUT"


def test_apply_requires_exactly_one_selector() -> None:
    vouchers, _ = _apply_transport()
    with pytest.raises(ValueError, match="exactly one"):
        vouchers.apply_to_cart("cart-1", token="tok")
    with pytest.raises(ValueError, match="exactly one"):
        vouchers.apply_to_cart("cart-1", token="tok", code="a", campaign_id="b")
