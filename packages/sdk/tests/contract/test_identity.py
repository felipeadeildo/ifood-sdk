"""Contrato de identidade: o que foi medido no login, sem repetir o desafio.

Três regras que este arquivo respeita:

1. **Nenhum teste aqui faz chamada de rede.** Login exige sessão e PX; aqui só se
   lê o que já foi capturado. Os testes de identidade não têm `--live` nem
   `--record` de propósito.
2. **O desafio é de uso único e expira em 60 s.** Um teste que repetisse
   ``POST /v2/identity-providers/OTP/authorization-codes`` queimaria o desafio do
   operador. Por isso o cassete é evidência, não coisa a reexecutar.
3. **Os valores medidos vivem em ``tests/fixtures/identity_contract.json``**, que é
   curado à mão e não tem PII. Os cassetes guardam forma, nunca token.

Fonte: ``evidence/login-01`` (captura de 2026-10-19T03:11Z) + leitura do bundle.
"""

import json
from pathlib import Path

import pytest
from support.pending.http import SENSITIVE_KEYS
from support.pending.web_paths import IDENTITY_ROUTES

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "identity_contract.json"
CASSETTES = Path(__file__).resolve().parents[1] / "cassettes" / "inventory"


def contract() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_login_is_passwordless_otp() -> None:
    """O web não usa senha nem OAuth2: é OTP por WhatsApp/SMS/e-mail."""
    facts = contract()
    assert facts["login_is_passwordless"] is True
    providers = facts["flows"]["providers"]["observed_names"]
    assert {"OTP_EMAIL", "OTP_WHATSAPP", "OTP_SMS"} <= set(providers)
    assert "PASSWORD" not in providers


def test_no_oauth_password_grant_in_the_declared_routes() -> None:
    """Não existe grant de senha: nenhuma rota declarada é ``/oauth/token``."""
    paths = [route.path for route in IDENTITY_ROUTES if route.confidence != "descartado"]
    assert "/oauth/token" not in paths
    assert all("/identity-providers" in path for path in paths)
    # O caminho sem versão que eu tinha lido no bundle não existe.
    assert not any(path == "/identity-providers/IFOOD/authentications" for path in paths)


def test_otp_chain_order_and_statuses() -> None:
    """A cadeia medida, na ordem: 201 → 201 → 200 → 201."""
    flows = contract()["flows"]
    assert flows["authorization_code"]["response"]["status"] == 201
    assert flows["challenge_token"]["response"]["status"] == 201
    assert flows["challenge_confirm"]["response"]["status"] == 200
    assert flows["authenticate"]["response"]["status"] == 201


def test_challenge_expires_in_sixty_seconds_and_is_single_use() -> None:
    """O número que muda o desenho: 60 s, ``key`` de uso único, sem retry."""
    flow = contract()["flows"]["authorization_code"]
    assert flow["timeout_seconds"] == 60
    assert flow["single_use"] is True
    assert "uso único" in flow["never_replay"]
    assert set(flow["response"]["keys"]) == {"key", "timeout_in_seconds"}


def test_authenticate_returns_session_jwt_and_refresh() -> None:
    keys = set(contract()["flows"]["authenticate"]["response"]["keys"])
    assert {"authenticated", "account_id", "access_token", "refresh_token"} <= keys
    assert "blocked_by_user" in keys, "conta bloqueada é caso de fluxo, não de erro"


def test_session_ttl_and_claims() -> None:
    """7200 s e claims do JWT: o refresh tem que ser proativo, não reativo."""
    session = contract()["session_model"]
    assert session["jwt_exp_minus_iat_seconds"] == 7200
    assert session["jwt_claims"]["iss"] == "iFood"
    assert session["jwt_claims"]["tenantId"] == "IFO"
    assert session["refresh"]["in_body"] is True
    assert set(session["refresh"]["cookies"]) == {"aAccessToken", "aRefreshToken"}


def test_auth_code_enters_in_exactly_one_place() -> None:
    """O código de 6 dígitos vai em ``/OTP/access-tokens`` e em lugar nenhum mais."""
    flow = contract()["flows"]["challenge_token"]
    assert flow["request"]["body_keys"] == ["key", "auth_code"]
    assert "nenhum outro lugar" in flow["auth_code_note"]


def test_phone_otp_is_confirmed_and_email_otp_is_unknown() -> None:
    """Telefone foi medido; e-mail falhou nos dois formatos. Não presumir simetria."""
    email = contract()["flows"]["authorization_code"]["email_variant"]
    assert email["status"] == "desconhecido"
    assert "não presumir simetria" in email["note"]


def test_identity_headers_are_mandatory() -> None:
    """Header faltando = 400 OTP-2000: passa a borda, falha na regra."""
    from support.pending.web_paths import IDENTITY_REQUIRED_HEADERS

    facts = contract()
    assert tuple(facts["identity_required_headers"]) == IDENTITY_REQUIRED_HEADERS
    assert "OTP-2000" in facts["identity_required_headers_note"]


def test_reorder_without_coordinates_is_flat_sco3000() -> None:
    """``SCO-3000`` é envelope plano e chega na regra, não na borda."""
    reorder = contract()["consumers"]["reorder_without_coordinates"]
    assert reorder["status"] == 400
    assert reorder["envelope"] == "flat"
    assert reorder["body"]["code"] == "SCO-3000"
    assert "PX" in reorder["note"]


def test_challenge_token_is_not_the_session_jwt() -> None:
    """Confundir os dois tokens é o erro clássico deste fluxo."""
    flows = contract()["flows"]
    assert flows["challenge_token"]["response"]["note"].startswith("token opaco")
    assert flows["authorization_code"]["response"]["status"] == 201


def test_customers_me_lives_on_the_bff_not_on_consumer_api() -> None:
    """``consumer-api/v1/customers/me`` deu 404 Kong; o web usa ``www/site-api``."""
    consumers = contract()["consumers"]
    assert consumers["me"]["status"] == 200
    assert consumers["me"]["needs_auth"] is True
    assert consumers["me_on_consumer_api"]["status"] == 404
    assert "site-api" in consumers["me_on_consumer_api"]["why"]


def test_px_is_per_endpoint_not_a_ttl() -> None:
    """Regra do ledger: fumaça de PX é por endpoint; não existe TTL único."""
    policy = contract()["px_policy"]
    assert "por endpoint" in policy
    assert "TTL" in policy


@pytest.mark.skipif(not CASSETTES.exists(), reason="inventário de login-01 não gerado")
def test_captured_identity_cassettes_carry_no_token_or_pii() -> None:
    """No cassete do OTP só entra a forma: ``key``, e-mail e tokens são ``<redacted>``."""
    identity = sorted(CASSETTES.glob("*identity_providers*.json"))
    assert len(identity) >= 4, f"esperava os 4 cassetes do OTP, achei {len(identity)}"

    for cassette in identity:
        payload = json.loads(cassette.read_text(encoding="utf-8"))
        body = payload["request"]["body"] or {}
        for key, value in body.items():
            if key.lower() in SENSITIVE_KEYS:
                assert value == "<redacted>", f"{cassette.name}: `{key}` com valor real"
        response = payload["response"]["json"]
        if isinstance(response, dict):
            for key, value in response.items():
                if key.lower() in SENSITIVE_KEYS:
                    assert value == "<redacted>", f"{cassette.name}: resposta vazando `{key}`"


def test_bff_requires_bearer_header_not_cookie() -> None:
    """O JWT vai em ``Authorization: Bearer``; o cookie sozinho devolve 401."""
    auth = contract()["authorization_header"]
    assert auth["format"].startswith("Bearer ")
    assert auth["source_cookie"] == "aAccessToken"
    assert auth["without_it"]["status"] == 401
    assert auth["without_it"]["body"]["message"] == "no jwt token"


def test_jar_updates_protocol_constants() -> None:
    """O jar carrega versão e chave do Faster: é como a lib sobrevive a deploy."""
    findings = contract()["jar_findings"]
    assert findings["derived_headers"]["aAppVersion"] == "app_version"
    assert findings["derived_headers"]["aFasterAppKey"] == "x-client-application-key"
    assert findings["saved_address_cookies"] == ["address-latitude", "address-longitude"]
    assert findings["device_payment_secret_cookie_prefix"] == "x-ifood-device-payment-"
