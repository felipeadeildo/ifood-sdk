import json
from pathlib import Path

import pytest

from ifood import (
    CART_MISSING,
    CART_WRONG_TYPE,
    Account,
    CartDraft,
    CartItem,
    CartPayloadError,
    SubItem,
    build_payload,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cart_v2_request.json"

ADDRESS = {
    "id": "addr-1",
    "coordinates": {"latitude": -23.56, "longitude": -46.65},
    "streetName": "Av. Paulista",
    "streetNumber": "1000",
    "neighborhood": "Bela Vista",
    "state": "SP",
    "city": "Sao Paulo",
    "zipCode": "01310100",
}


def draft(**overrides: object) -> CartDraft:
    base = {
        "merchant_id": "merchant-1",
        "merchant_name": "Pizza Prime",
        "address": ADDRESS,
        "items": (CartItem("item-1", 1, SubItem("opt-1"), observation="."),),
        "account": Account("acc-1", "User", "a@b.com", 55, "11", "900000000"),
    }
    base.update(overrides)
    return CartDraft(**base)  # type: ignore[arg-type]


def test_v2_carries_sub_items_and_account() -> None:
    payload = build_payload(draft(), "v2")
    assert payload["items"][0]["subItems"] == [{"id": "opt-1", "quantity": 1}]
    assert payload["items"][0]["observation"] == "."
    assert payload["delivery"] == {"id": "DEFAULT", "now": True, "deliveryBy": "IFOOD"}
    assert payload["account"]["id"] == "acc-1"
    assert payload["source"]["parameters"][0]["value"] == "9.178.5"


def test_v1_uses_garnish_and_a_string_for_now() -> None:
    payload = build_payload(draft(), "v1")
    assert payload["items"][0]["garnish"] == [{"id": "opt-1", "quantity": 1}]
    assert payload["delivery"]["now"] == "true"
    assert payload["delivery"]["mode"] == "DELIVERY"
    assert "account" not in payload


def test_v2_without_account_is_refused() -> None:
    with pytest.raises(CartPayloadError) as caught:
        build_payload(draft(account=None), "v2")
    assert caught.value.code == CART_MISSING
    assert caught.value.field_name == "account"


def test_mixing_the_two_contracts_is_refused() -> None:
    payload = build_payload(draft(), "v2")
    payload["items"][0]["garnish"] = []
    with pytest.raises(CartPayloadError) as caught:
        build_payload(draft(), "v1") if False else None
        from ifood import validate_payload

        validate_payload(payload, version="v2")
    assert caught.value.code == CART_WRONG_TYPE


def test_empty_items_are_refused() -> None:
    with pytest.raises(CartPayloadError) as caught:
        build_payload(draft(items=()), "v2")
    assert caught.value.code == CART_MISSING
    assert caught.value.field_name == "items"


def test_built_payload_matches_the_shape_the_server_accepted() -> None:
    if not FIXTURE.exists():
        pytest.skip("captured cart payload is not in this checkout")
    real = json.loads(FIXTURE.read_text())
    built = build_payload(draft(), "v2")
    assert set(built) == set(real)
    assert set(built["items"][0]) == set(real["items"][0])
    assert set(built["delivery"]) == set(real["delivery"])
    assert built["items"][0]["subItems"][0].keys() == real["items"][0]["subItems"][0].keys()
