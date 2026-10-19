"""Contrato de ``marketplace /v1/merchants/{uuid}``.

O que protege: a rota existe sem autenticação (só com os headers de app), o
código de recusa de merchant inexistente (``IFCS-2001``) e o fato de
``channel`` ser obrigatório. O uuid usado é inventado de propósito: nenhum
teste aqui toca pedido, carrinho ou dado de usuário.
"""

import pytest
from support.pending.errors import IfoodApiError

MERCHANT = "/v1/merchants/{uuid}"
#: UUID nil: o formato é válido e o merchant certamente não existe.
UNKNOWN_UUID = "00000000-0000-4000-8000-000000000000"


def test_merchant_unknown_uuid_is_404_ifcs2001(client) -> None:
    response = client.get("marketplace", MERCHANT.format(uuid=UNKNOWN_UUID), channel="IFOOD")
    assert response.status_code == 404, response.text[:300]

    error = IfoodApiError.from_response(response.status_code, str(response.url), response.text)
    assert error is not None
    assert error.code == "IFCS-2001", f"código mudou: {response.text[:300]}"


def test_merchant_without_channel_is_400(client) -> None:
    """Sem ``channel`` o serviço recusa antes de procurar o merchant."""
    response = client.get("marketplace", MERCHANT.format(uuid=UNKNOWN_UUID))
    assert response.status_code == 400, response.text[:300]
    assert response.status_code != 404, (
        "sem channel virou 'não encontrado': some o sinal de erro de cliente"
    )


@pytest.mark.live
def test_merchant_error_shape_matches_cassette(client) -> None:
    import json

    from contract.conftest import CASSETTES, json_shape

    recorded = json.loads(
        (CASSETTES / "test_merchant_unknown_uuid_is_404_ifcs2001.json").read_text(encoding="utf-8")
    )
    response = client.get("marketplace", MERCHANT.format(uuid=UNKNOWN_UUID), channel="IFOOD")
    assert response.status_code == 404
    assert json_shape(response.json()) == json_shape(recorded["response"]["json"]), (
        "shape do 404 mudou"
    )
