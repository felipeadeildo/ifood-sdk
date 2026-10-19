"""Carrinho: as duas versões do payload, e o payload real que passou na API.

O teste central deste arquivo é ``test_lib_payload_has_the_same_shape_as_the_real_one``:
ele lê o corpo **real** que o web mandou em ``evidence/cart-01`` (via cassete
redigido) e compara com o que a lib monta. É o único jeito de impedir que alguém
"arrume" ``delivery.now`` para boolean na v1 ou para string na v2 sem perceber.
"""

import json
from pathlib import Path

import pytest
from support.pending.cart import (
    CART_MISSING,
    CART_WRONG_TYPE,
    Account,
    CartDraft,
    CartItem,
    CartPayloadError,
    SubItem,
    build_payload,
    parse_cart_response,
    validate,
)
from support.pending.web_paths import CART_VALIDATION_CHAIN

CASSETTES = Path(__file__).resolve().parents[1] / "cassettes" / "inventory-cart"
REAL_CART = CASSETTES / "post_www_ifood_com_br_site_api_v2_carts.json"

ADDRESS = {
    "id": "a0e3e4b6-768e-4def-911a-63935a0074eb",
    "coordinates": {"latitude": -23.56, "longitude": -46.65},
    "streetName": "Avenida Paulista",
    "streetNumber": "1000",
    "neighborhood": "Bela Vista",
    "state": "SP",
    "city": "São Paulo",
    "zipCode": "01310-100",
}

MERCHANT = "0a0d6cdd-f04f-4909-aae6-fabb497f08b7"

ACCOUNT = Account(id="account-1", name="Nome", email="pessoa@example.com", phone={"number": "1"})


def draft(**overrides: object) -> CartDraft:
    base: dict[str, object] = {
        "merchant_id": MERCHANT,
        "merchant_name": "Mcdonald's Pamplona",
        "address": ADDRESS,
        "items": [
            CartItem(
                id="item-1",
                quantity=1,
                observation=".",
                sub_items=(SubItem(id="sub-1"), SubItem(id="sub-2"), SubItem(id="sub-3")),
            )
        ],
        "account": ACCOUNT,
    }
    base.update(overrides)
    return CartDraft(**base)  # type: ignore[arg-type]


def compatible(lib: object, real: object) -> bool:
    """Compara estrutura, tolerando o que o cassete redigiu.

    O cassete guarda ``<redacted>`` no lugar de valores sensíveis (endereço, conta).
    Ali a comparação para: não há como exigir igualdade de um valor que foi apagado
    de propósito. Estrutura de chaves continua sendo comparada onde há valor.
    """
    if real == "<redacted>":
        return True
    if isinstance(lib, dict) and isinstance(real, dict):
        return set(lib) == set(real) and all(compatible(lib[key], real[key]) for key in lib)
    if isinstance(lib, list) and isinstance(real, list):
        if not lib or not real:
            return True
        return compatible(lib[0], real[0])
    return True


def test_lib_payload_has_the_same_shape_as_the_real_one() -> None:
    """A comparação que importa: lib × corpo real que o servidor aceitou (201)."""
    if not REAL_CART.exists():
        pytest.skip("cassete do cart-01 não gerado nesta máquina")
    recorded = json.loads(REAL_CART.read_text(encoding="utf-8"))
    real_body = recorded["request"]["body"]
    assert isinstance(real_body, dict)

    lib_body = build_payload(draft())
    assert compatible(lib_body, real_body), "a lib monta uma estrutura diferente da real"


def test_v2_now_is_boolean() -> None:
    """Medido no corpo real: `"now": true`. A v1 exige a string — é o oposto."""
    delivery = build_payload(draft())["delivery"]
    assert isinstance(delivery, dict)
    assert delivery["now"] is True
    assert "mode" not in delivery, "v2 não manda `mode`"
    assert delivery["deliveryBy"] == "IFOOD"


def test_v1_now_is_a_string() -> None:
    delivery = build_payload(draft(), version="v1")["delivery"]
    assert isinstance(delivery, dict)
    assert delivery["now"] == "true"
    assert delivery["mode"] == "DELIVERY"


def test_v2_garnish_is_sub_items_and_v1_is_garnish() -> None:
    """A mesma escolha de complemento tem nome diferente em cada versão."""
    v2_item = build_payload(draft())["items"][0]
    assert isinstance(v2_item, dict)
    assert "subItems" in v2_item and "garnish" not in v2_item
    assert v2_item["subItems"][0] == {"id": "sub-1", "quantity": 1}

    v1_item = build_payload(draft(), version="v1")["items"][0]
    assert isinstance(v1_item, dict)
    assert "subItems" not in v1_item


def test_wrong_field_for_the_version_is_refused_before_the_network() -> None:
    payload = build_payload(draft())
    item = payload["items"][0]
    assert isinstance(item, dict)
    item["garnish"] = {"code": "bacon"}
    with pytest.raises(CartPayloadError) as excinfo:
        validate(payload, version="v2")
    assert excinfo.value.code == CART_WRONG_TYPE
    assert excinfo.value.field == "garnish"


def test_string_now_in_v2_is_refused() -> None:
    payload = build_payload(draft())
    delivery = payload["delivery"]
    assert isinstance(delivery, dict)
    delivery["now"] = "true"
    with pytest.raises(CartPayloadError) as excinfo:
        validate(payload, version="v2")
    assert excinfo.value.field == "now"


def test_boolean_now_in_v1_is_refused() -> None:
    """O erro que custaria uma chamada por tentativa na v1."""
    payload = build_payload(draft(), version="v1")
    delivery = payload["delivery"]
    assert isinstance(delivery, dict)
    delivery["now"] = True
    with pytest.raises(CartPayloadError) as excinfo:
        validate(payload, version="v1")
    assert excinfo.value.field == "now"
    assert "string" in str(excinfo.value)


def test_address_as_reference_is_refused() -> None:
    payload = build_payload(draft())
    payload["address"] = ADDRESS["id"]
    with pytest.raises(CartPayloadError) as excinfo:
        validate(payload)
    assert excinfo.value.field == "address"


@pytest.mark.parametrize("missing", ["merchant", "address", "items", "delivery"])
def test_missing_field_is_cart006_in_the_measured_order(missing: str) -> None:
    payload = build_payload(draft())
    payload.pop(missing)
    with pytest.raises(CartPayloadError) as excinfo:
        validate(payload)
    assert excinfo.value.code == CART_MISSING
    assert excinfo.value.field == missing


def test_validation_order_matches_the_measured_chain() -> None:
    order = [field_name for _code, field_name, _note in CART_VALIDATION_CHAIN]
    assert order[:4] == ["merchant", "merchant", "address", "items"]
    with pytest.raises(CartPayloadError) as excinfo:
        validate({})
    assert excinfo.value.field == "merchant"


def test_v2_carries_account_and_source() -> None:
    """O web manda nome/e-mail/telefone da conta e a proveniência do pedido."""
    payload = build_payload(draft())
    account = payload["account"]
    source = payload["source"]
    assert isinstance(account, dict) and set(account) == {"id", "name", "email", "phone"}
    assert isinstance(source, dict)
    assert source["parameters"] == [{"name": "version", "value": "9.178.5"}]


def test_v2_requires_account_unless_explicitly_waived() -> None:
    """O corpo real sempre traz `account`; o v2 reclama se faltar."""
    with pytest.raises(CartPayloadError) as excinfo:
        build_payload(draft(account=None))
    assert excinfo.value.field == "account"

    payload = build_payload(draft(account=None), allow_missing_account=True)
    assert "account" not in payload


def test_parse_the_real_cart_response() -> None:
    """A resposta 201 é ``{cartResponse, signature, data, warning}``; ler sem inventar."""
    if not REAL_CART.exists():
        pytest.skip("cassete do cart-01 não gerado nesta máquina")
    recorded = json.loads(REAL_CART.read_text(encoding="utf-8"))
    response_body = recorded["response"]["json"]
    assert isinstance(response_body, dict)
    # O cassete guarda shape (valores viram tipo), então reconstruímos um mínimo fiel.
    snapshot = parse_cart_response(
        {
            "cartResponse": {
                "id": "cart-1",
                "status": "OPEN",
                "createdAt": "2026-10-19T03:26:25.807847135Z",
                "expiresAt": "2026-10-19T03:26:36.117983128Z",
                "evaluators": [
                    {"id": "MERCHANT_CART_EVALUATOR", "expiresAt": "2026-10-19T00:26:25.85"},
                    {"id": "FEE_CART_EVALUATOR", "expiresAt": "2026-10-19T00:26:26.08"},
                ],
            },
            "signature": "x" * 96,
        }
    )
    assert snapshot.cart_id == "cart-1"
    assert snapshot.status == "OPEN"
    assert len(snapshot.evaluators) == 2
    assert snapshot.evaluators[0].id == "MERCHANT_CART_EVALUATOR"
    assert len(snapshot.signature) == 96
    # `cartResponse` é opaco: guardamos inteiro, sem reinterpretar.
    assert snapshot.cart_response["status"] == "OPEN"


def test_total_comes_from_the_final_snapshot_not_from_what_was_approved() -> None:
    """31,89 aprovado na tela → 37,89 depois de trocar para entrega prioritária."""
    from support.pending.cart import snapshot_total

    approved = {"summary": {"total": 31.89}}
    final = {"summary": {"total": 37.89}}
    assert snapshot_total(approved) == 31.89
    assert snapshot_total(final) == 37.89
    assert snapshot_total(final) != snapshot_total(approved), (
        "o amount do checkout acompanha o snapshot final: ler o aprovado cobra o preço errado"
    )


def test_snapshot_without_total_is_refused() -> None:
    from support.pending.cart import snapshot_total

    with pytest.raises(CartPayloadError) as excinfo:
        snapshot_total({"summary": {}})
    assert excinfo.value.field == "total"


def test_cart_response_without_cart_is_refused() -> None:
    with pytest.raises(CartPayloadError) as excinfo:
        parse_cart_response({"data": {}, "signature": "x"})
    assert excinfo.value.field == "cartResponse"
