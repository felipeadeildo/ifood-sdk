"""Contrato do geocode de endereço (``logistics-api``).

O que este arquivo protege: o shape de ``rules[]``/``addresses[]`` e o fato de o
serviço devolver coordenada para endereço com rua. Se o iFood mudar o nome de
um campo, o app do operador quebra silenciosamente — aqui quebra alto.
"""

import pytest
from support.pending.http import Json, dig
from support.shape import json_shape

GEOCODE = "/location/v1/addresses:geocode"
FULL_ADDRESS = "Avenida Paulista, 1000 - Bela Vista, São Paulo - SP, Brasil"
STREET_ONLY = "Rua Augusta, São Paulo - SP"
GARBAGE = "asdkjhasd qweqwe 9999 zzz"

#: Campos que o app usa para montar o endereço; some um, some a tela.
RULE_KEYS = {
    "city",
    "state",
    "country",
    "streetName",
    "streetNumber",
    "neighborhood",
    "coordinates",
}
#: São Paulo, Bela Vista. Serve só como sanidade, não como igualdade exata.
PAULISTA = (-23.5613, -46.6565)


def _geocode(client, query: str) -> tuple[int, Json]:
    response = client.get("logistics", GEOCODE, query=query)
    return response.status_code, response.json()


def test_geocode_full_address(client) -> None:
    status, payload = _geocode(client, FULL_ADDRESS)
    assert status == 200

    rules = dig(payload, "rules")
    assert isinstance(rules, list)
    keys = {rule["key"] for rule in rules if isinstance(rule, dict) and "key" in rule}
    assert keys >= RULE_KEYS, f"regras faltando: {sorted(RULE_KEYS - keys)}"
    required = {rule["key"]: rule.get("required") for rule in rules if isinstance(rule, dict)}
    assert required["streetNumber"] is False, "número virou obrigatório: muda o fluxo de digitação"
    assert required["streetName"] is True

    address = dig(payload, "addresses.0")
    assert isinstance(address, dict)
    latitude = dig(address, "coordinates.latitude")
    longitude = dig(address, "coordinates.longitude")
    assert isinstance(latitude, int | float) and isinstance(longitude, int | float)
    assert abs(latitude - PAULISTA[0]) < 0.05, f"latitude fora de São Paulo: {latitude}"
    assert abs(longitude - PAULISTA[1]) < 0.05, f"longitude fora de São Paulo: {longitude}"


def test_geocode_street_only_returns_candidate(client) -> None:
    """Sem número o serviço ainda responde 200 e devolve um candidato.

    Atenção ao que foi observado no cassete: perguntando só "Rua Augusta, São
    Paulo - SP" o serviço devolveu ``streetNumber: "1559"``, ou seja ele
    **inventa um número**. O cliente não pode tratar esse número como
    confirmado pelo usuário; ele serve no máximo de sugestão.
    """
    status, payload = _geocode(client, STREET_ONLY)
    assert status == 200
    addresses = dig(payload, "addresses")
    assert isinstance(addresses, list) and addresses, "rua sem número deixou de ser geocodificável"
    address = addresses[0]
    assert isinstance(address, dict)
    assert dig(address, "coordinates.latitude") is not None
    assert dig(address, "streetName"), "rua sem número deveria voltar com streetName preenchido"


def test_geocode_garbage_is_404_ifsl2002(client) -> None:
    """Lixo não vira lista vazia: é 404 ``IFSL-2002``.

    O cliente não pode confundir "endereço não encontrado" com falha de rede nem
    com 5xx — o fluxo de digitação precisa mostrar "não achei" ao usuário.
    Curiosidade registrada: ``details`` vaza o provedor (``HERE``).
    """
    status, payload = _geocode(client, GARBAGE)
    assert status == 404, payload
    assert status < 500
    assert dig(payload, "code") == "IFSL-2002"


def test_geocode_without_application_key_is_401(client) -> None:
    response = client.get("logistics", GEOCODE, application_key=False, query=FULL_ADDRESS)
    assert response.status_code == 401, response.text[:300]
    body = response.text
    assert "IFSL-2004" in body, f"código de erro mudou: {body[:300]}"
    # O código também vem no header: dá para decidir sem parsear o corpo.
    assert response.headers.get("x-ifood-error-code") == "IFSL-2004"


@pytest.mark.live
def test_geocode_shape_matches_cassette(client) -> None:
    """Deriva de contrato: só roda com --live/--record e compara o esqueleto."""
    import json

    from contract.conftest import CASSETTES

    recorded = json.loads(
        (CASSETTES / "test_geocode_full_address.json").read_text(encoding="utf-8")
    )
    status, payload = _geocode(client, FULL_ADDRESS)
    assert status == 200
    assert json_shape(payload) == json_shape(recorded["response"]["json"]), "shape do geocode mudou"
