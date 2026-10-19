"""Testes do inventário de capturas.

O inventário é a ferramenta que transforma captura crua em contrato, então ele
mesmo precisa de teste: se ele parear errado, o ledger passa a mentir. Usa um
jsonl sintético, sem rede e sem dado de usuário.
"""

import json
from pathlib import Path

from support.inventory import (
    Exchange,
    is_static,
    load_events,
    normalize_path,
    pair_exchanges,
    representative,
    slug,
    summarize,
    to_cassette,
)

UUID = "5f2b1f5e-8f3a-4c62-9c4e-1b2a3c4d5e6f"


def _capture(tmp_path: Path) -> Path:
    events = [
        {
            "seq": 0,
            "type": "request",
            "method": "GET",
            "url": f"https://marketplace.ifood.com.br/v1/merchants/{UUID}?channel=IFOOD",
            "headers": {
                "user-agent": "x",
                "x-ifood-session-id": "s",
                "referer": "https://www.ifood.com.br/",
            },
            "postData": None,
            "at": "2026-10-19T03:00:00Z",
        },
        {
            "seq": 1,
            "type": "response",
            "method": "GET",
            "url": f"https://marketplace.ifood.com.br/v1/merchants/{UUID}?channel=IFOOD",
            "status": 404,
            "headers": {"content-type": "application/json; charset=utf-8"},
            "body": '{"code": "IFCS-2001", "message": "Merchant not found", "details": []}',
        },
        {
            "seq": 2,
            "type": "request",
            "method": "GET",
            "url": "https://logistics-api.ifood.com.br/location/v1/addresses:geocode?query=Pizza",
            "headers": {"user-agent": "x"},
            "at": "2026-10-19T03:00:01Z",
        },
        {
            "seq": 3,
            "type": "response",
            "method": "GET",
            "url": "https://logistics-api.ifood.com.br/location/v1/addresses:geocode?query=Pizza",
            "status": 200,
            "headers": {"content-type": "application/json"},
            "body": '{"rules": [], "addresses": [{"coordinates": {"latitude": -23.5, "longitude": -46.6}}]}',
        },
        # Mesmo endpoint com outro uuid: tem que agrupar.
        {
            "seq": 4,
            "type": "request",
            "method": "GET",
            "url": f"https://marketplace.ifood.com.br/v1/merchants/{UUID}?channel=IFOOD",
            "headers": {"user-agent": "x"},
        },
        {
            "seq": 5,
            "type": "response",
            "method": "GET",
            "url": f"https://marketplace.ifood.com.br/v1/merchants/{UUID}?channel=IFOOD",
            "status": 404,
            "headers": {"content-type": "application/json"},
            "body": '{"code": "IFCS-2001"}',
        },
        # Resposta sem requisição: órfã, não pode sumir silenciosamente.
        {
            "seq": 6,
            "type": "response",
            "method": "GET",
            "url": "https://x.ifood.com.br/sem-par",
            "status": 500,
            "headers": {},
            "body": "",
        },
        # Estáticos: fora do inventário.
        {
            "seq": 7,
            "type": "request",
            "method": "GET",
            "url": "https://www.ifood.com.br/_next/static/chunk.js",
            "headers": {},
        },
        {
            "seq": 8,
            "type": "response",
            "method": "GET",
            "url": "https://www.ifood.com.br/_next/static/chunk.js",
            "status": 200,
            "headers": {"content-type": "application/javascript"},
            "body": "console.log(1)",
        },
        # Linha quebrada não pode derrubar o parser.
        {"type": "response", "method": "GET"},
    ]
    path = tmp_path / "requests.jsonl"
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    return path


def test_normalize_path_replaces_identity() -> None:
    assert normalize_path(f"/v1/merchants/{UUID}/menu") == "/v1/merchants/{uuid}/menu"
    assert normalize_path("/v1/sections/1234") == "/v1/sections/{n}"
    assert (
        normalize_path("/eng5outu/JAtdqSvnXgtFS5-pSOgQa12jgZsWUwbjOc9hWkqEornV4pTY")
        == "/eng5outu/{token}"
    )
    assert normalize_path("/v1/merchants") == "/v1/merchants"


def test_static_and_non_http_are_noise() -> None:
    assert is_static("https://www.ifood.com.br/app.css")
    assert is_static("blob:https://www.ifood.com.br/abc")
    assert is_static("https://www.ifood.com.br/cdn-cgi/challenge-platform/h/b/orchestrate")
    assert not is_static("https://marketplace.ifood.com.br/v1/merchants/x?channel=IFOOD")


def test_pairing_groups_by_route_and_counts_orphans(tmp_path: Path) -> None:
    exchanges, orphans = pair_exchanges(load_events(_capture(tmp_path)))
    assert orphans == 1, "resposta sem requisição deveria contar como órfã"
    # O pareamento não filtra estático (quem filtra é summarize); são 4 pares com resposta.
    with_status = [exchange for exchange in exchanges if exchange.status is not None]
    assert len(with_status) == 4

    endpoints = summarize(exchanges)
    keys = {endpoint.key for endpoint in endpoints}
    assert keys == {
        "GET marketplace.ifood.com.br/v1/merchants/{uuid}",
        "GET logistics-api.ifood.com.br/location/v1/addresses:geocode",
    }
    merchant = next(endpoint for endpoint in endpoints if "merchants" in endpoint.path)
    assert merchant.count == 2, "duas chamadas ao mesmo merchant deveriam agrupar"
    assert merchant.statuses[404] == 2
    assert merchant.query_keys == {"channel"}
    # Só a primeira chamada trouxe referer no captura sintética.
    assert merchant.initiators == {"https://www.ifood.com.br/": 1}
    assert "x-ifood-session-id" in merchant.request_header_keys


def test_cassette_never_carries_secrets_but_keeps_parameter_names(tmp_path: Path) -> None:
    """Token e senha não podem sair na captura; o *nome* do parâmetro é contrato."""

    exchange = Exchange(
        method="POST",
        url="https://www.ifood.com.br/site-api/v3/identity-providers/IFOOD/authentications",
        status=200,
        request_headers={"content-type": "application/x-www-form-urlencoded"},
        request_body="email=alguem@example.com&password=segredo123&device_id=abc&grant_type=password",
        response_headers={"content-type": "application/json"},
        response_body='{"access_token": "eyJhbGciOi.real", "refresh_token": "r3al", "expires_in": 3600}',
    )
    cassette = to_cassette(exchange, name="login")
    request = cassette["request"]
    assert isinstance(request, dict)
    body = request["body"]
    assert isinstance(body, dict)

    # Nomes preservados, valores sensíveis trocados.
    assert body["email"] == "<redacted>"
    assert body["password"] == "<redacted>"
    assert body["grant_type"] == "password", "valor não-sensível é o que responde 'qual grant'"
    # device_id identifica o aparelho do operador: é PII, vai redigido.
    assert body["device_id"] == "<redacted>"

    response = cassette["response"]
    assert isinstance(response, dict)
    payload = response["json"]
    assert isinstance(payload, dict)
    assert payload["access_token"] == "<redacted>"
    assert payload["refresh_token"] == "<redacted>"
    assert payload["expires_in"] == "<number>"

    dumped = json.dumps(cassette)
    assert "segredo123" not in dumped
    assert "eyJhbGciOi.real" not in dumped
    assert "alguem@example.com" not in dumped


def test_cassette_from_a_real_exchange_is_usable(tmp_path: Path) -> None:
    exchanges, _orphans = pair_exchanges(load_events(_capture(tmp_path)))
    endpoints = summarize(exchanges)

    merchant = next(endpoint for endpoint in endpoints if "merchants" in endpoint.path)
    exchange = representative(exchanges, merchant)
    assert exchange is not None
    # representative prefere sucesso; aqui só há 404, então cai no fallback.
    assert exchange.status == 404
    cassette = to_cassette(exchange, name=slug(merchant))
    assert cassette["schema"] == 1
    response = cassette["response"]
    assert isinstance(response, dict)
    assert response["status"] == 404
