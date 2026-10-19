"""Os três envelopes de erro, como contrato.

Motivo: o cliente vai decidir retry/reportar a partir destes campos. Se o parser
só ler ``body["code"]``, o envelope aninhado (``{"error":{"code":...}}``) do
carrinho vira "erro desconhecido" e o fluxo quebra com mensagem inútil.

Nada aqui toca a rede: os corpos literais estão em
``tests/fixtures/error_envelopes.json``, medidos em captura.
"""

import json
from pathlib import Path

import pytest
from support.pending.errors import (
    ENVELOPE_EDGE,
    ENVELOPE_FLAT,
    ENVELOPE_KONG,
    ENVELOPE_NESTED,
    IfoodApiError,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "error_envelopes.json"


def envelopes() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["envelopes"]


def _error(name: str) -> IfoodApiError:
    case = envelopes()[name]["example"]
    body = case["body"] if isinstance(case["body"], str) else json.dumps(case["body"])
    error = IfoodApiError.from_response(
        case["status"], "https://exemplo", body, response_headers=case["headers"]
    )
    assert error is not None
    return error


def test_flat_envelope_keeps_code_and_details() -> None:
    """IFCS/IFSL: código no corpo *e* no header, com ``details`` útil."""
    error = _error("flat")
    assert error.envelope == ENVELOPE_FLAT
    assert error.code == "IFCS-2001"
    assert error.message == "Merchant not found"
    assert error.details and "ids not found" in error.details[0]
    assert error.is_business_rule is True
    assert error.retryable is False, "regra de negócio não é retry"


def test_nested_envelope_is_the_one_that_breaks_naive_clients() -> None:
    """CART/ITEM/SCO usam ``{"error": {...}}`` — o código não está no topo."""
    error = _error("nested")
    assert error.envelope == ENVELOPE_NESTED
    assert error.code == "CART-006"
    assert error.message == "merchant is required"
    assert error.is_business_rule is True


def test_kong_is_not_a_business_error() -> None:
    """``{"message":"Not Found"}`` = rota não registrada no host."""
    error = _error("kong")
    assert error.envelope == ENVELOPE_KONG
    assert error.is_edge is True
    assert error.is_business_rule is False
    assert error.code is None


def test_edge_challenge_is_not_the_api_speaking() -> None:
    """403 com ``cf-mitigated`` é PX/CF; asserção de contrato aqui é ruído (R0)."""
    error = _error("edge")
    assert error.envelope == ENVELOPE_EDGE
    assert error.is_edge is True
    assert error.retryable is False


def test_rate_limit_is_retryable_and_has_no_retry_after() -> None:
    """429 do marketplace: único caso retryable de 4xx, e sem ``Retry-After``."""
    error = IfoodApiError.from_response(
        429, "https://exemplo", '{"message": "API rate limit exceeded"}'
    )
    assert error is not None
    assert error.is_rate_limited is True
    assert error.retryable is True


def test_server_error_is_retryable() -> None:
    error = IfoodApiError.from_response(503, "https://exemplo", "<html>unavailable</html>")
    assert error is not None
    assert error.retryable is True


def test_header_code_is_used_when_body_has_none() -> None:
    """``x-ifood-error-code`` salva o caso de corpo sem ``code``."""
    error = IfoodApiError.from_response(
        400,
        "https://exemplo",
        '{"message": "algo"}',
        response_headers={"x-ifood-error-code": "IFSL-2004"},
    )
    assert error is not None
    assert error.code == "IFSL-2004"
    assert error.header_code == "IFSL-2004"


def test_checkout_chain_is_encoded_in_order() -> None:
    """A cadeia de validação do carrinho é contrato: cada passo, um código."""
    chain = json.loads(FIXTURE.read_text(encoding="utf-8"))["checkout_chain"]
    codes = [step["code"] for step in chain["steps"]]
    assert codes[0] == "CART-006"
    assert "CART-007" in codes
    assert codes[-1] == "ITEM-001"
    assert chain["valid_payload_shape"]["delivery"]["now"] == "true", "string, não boolean"
    assert "access_key" in chain["headers"], "cart leva as chaves estáticas da WSV3"


def test_reorder_requires_coordinates() -> None:
    """Sem ``lat``/``lon`` o reorder recusa com ``SCO-3000``."""
    reorder = json.loads(FIXTURE.read_text(encoding="utf-8"))["reorder"]
    assert reorder["query"] == ["lat", "lon"]
    assert reorder["without_coords"]["status"] == 400
    assert reorder["without_coords"]["code"] == "SCO-3000"
    assert "desconhecido" in reorder["without_coords"]["envelope"]


@pytest.mark.parametrize("status", [200, 201, 204, 301])
def test_success_statuses_do_not_raise(status: int) -> None:
    assert IfoodApiError.from_response(status, "https://exemplo", "") is None


def test_web_paths_and_fixture_agree_on_the_cart_chain() -> None:
    """Duas verdades sobre a mesma cadeia é bug esperando acontecer: comparar."""
    from support.pending.web_paths import CART_CREATE_PAYLOAD, CART_VALIDATION_CHAIN

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["checkout_chain"]
    fixture_codes = [step["code"] for step in fixture["steps"]]
    module_codes = [code for code, _field, _note in CART_VALIDATION_CHAIN]
    assert module_codes == fixture_codes
    assert CART_CREATE_PAYLOAD["delivery"]["now"] == "true"
    assert fixture["valid_payload_shape"]["delivery"]["now"] == "true"


def test_every_declared_cart_route_has_a_base_placeholder() -> None:
    """``{base}`` é o que permite v1/v2: rota sem placeholder seria inconsistência."""
    from support.pending.web_paths import CART_BASES, CART_ROUTES

    for route in CART_ROUTES:
        if route.path.startswith("/"):
            assert route.path.startswith("/v1/carts"), f"{route.name}: path absoluto fora do padrão"
        else:
            assert "{base}" in route.path, f"{route.name}: sem {{base}}"
    assert CART_BASES == ("/v1/carts", "/v2/carts")


def test_bff_401_without_bearer_is_its_own_case() -> None:
    """``{"message":"no jwt token"}``: plano, sem ``code``, e é falta de header."""
    error = IfoodApiError.from_response(401, "https://exemplo", '{"message": "no jwt token"}')
    assert error is not None
    assert error.code is None, "não há código de aplicação aqui"
    assert error.is_auth_missing is True
    assert error.is_business_rule is False
    assert error.retryable is False, "repetir sem o header dá o mesmo 401"


def test_edge_403_is_not_auth_missing() -> None:
    """Não confundir borda com falta de token: conserto diferente."""
    error = _error("edge")
    assert error.is_auth_missing is False
