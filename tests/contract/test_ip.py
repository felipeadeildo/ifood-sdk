"""Contrato de ``consumer-api /ip`` e do conjunto canônico de headers.

``/ip`` é a rota mais barata do inventário e serve de canário: se ela cai, ou se
o conjunto de headers de app deixa de passar, tudo o mais cai junto.
"""

import ipaddress

from support.pending.config import APP_VERSION, app_headers


def test_ip_returns_valid_address(client) -> None:
    response = client.get("consumer", "/ip")
    assert response.status_code == 200, response.text[:300]
    payload = response.json()
    assert isinstance(payload, dict)
    raw = payload.get("ip")
    assert isinstance(raw, str)
    address = ipaddress.ip_address(raw)
    # O cassete grava o IP já anonimizado (203.0.113.7). Em --live tem que ser público.
    if raw != "203.0.113.7":
        assert not address.is_private, f"IP privado devolvido: {raw}"


def test_app_headers_are_the_observed_set() -> None:
    """O header canônico não muda sem alguém decidir mudar."""
    headers = app_headers("sessao-de-teste", "device-de-teste")
    assert headers["app_name"] == "consumer_webapp"
    assert headers["platform"] == "webapp"
    assert headers["app_version"] == APP_VERSION
    assert headers["country"] == "br"
    assert headers["x-ifood-session-id"] == "sessao-de-teste"
    assert headers["x-ifood-device-id"] == "device-de-teste"
    # Chaves estáticas do web app: se sumirem, o 401 IFSL-2004 volta em tudo.
    assert headers["x-application-key"]
    assert headers["x-client-application-key"]


def test_session_and_device_ids_differ_per_client() -> None:
    from support.pending.http import ContractClient

    first, second = ContractClient(), ContractClient()
    assert first.session_id != second.session_id
    assert first.device_id != second.device_id
    first.close()
    second.close()
