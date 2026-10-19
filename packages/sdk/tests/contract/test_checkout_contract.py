"""Contrato do checkout, com a confiança de cada campo declarada.

Motivo de existir: é a parte do fluxo onde errar custa dinheiro do operador. Aqui
nada é afirmado como contrato se não foi medido — e o que é inferido fica marcado,
porque um teste que "sabe" demais sobre idempotência é pior que teste nenhum.

Fatos medidos pelo `ifood-api` (bundle + captura):
- o segredo de pagamento é o **valor do cookie** `x-ifood-device-payment-<sha>`,
  sem transformação, e o jar do web já o tem → cartão salvo não exige Android;
- `cartResponse` vem assinado **do servidor** e é opaco;
- `validationVersion` é string opaca gerada no cliente;
- não existe leitura de carrinho no bundle.
"""

import json
import os
from pathlib import Path

import pytest
from support.pending.session import Session, read_jar
from support.pending.web_paths import CHECKOUT_HEADERS, CHECKOUT_INTEGRITY, GARNISH_VARIANTS

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "checkout_contract.json"
JAR = Path(os.environ.get("IFOOD_JAR", Path.home() / ".config" / "ifood-sdk" / "session.jar"))


def contract() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def contract_v2() -> dict:
    return json.loads(V2.read_text(encoding="utf-8"))


def test_payment_amount_lives_on_the_source_not_the_method() -> None:
    """Armadilha de leitura: ``amount`` é da fonte (``sources[]``), não do método."""
    shape = contract_v2()["checkout"]["body_shape"]["paymentSources"]["sources"][0]
    assert set(shape) == {"source", "amount", "additionalData", "paymentMethod"}
    assert shape["amount"] == {"value": "number", "currency": "BRL"}
    assert "amount" not in shape["paymentMethod"]
    notes = contract_v2()["checkout"]["payment_notes"]
    assert notes["amount_location"].startswith("sources[].amount")
    assert "37.89" in notes["amount_equals"]


def test_device_payment_header_was_sent_even_on_pix() -> None:
    """Correção de rótulo: 'Pix não precisa' é inferência; 'não envia' é falso."""
    notes = contract_v2()["checkout"]["payment_notes"]
    assert "MEDIDO enviou" in notes["device_header_on_pix"]
    assert "falso na captura" in notes["device_header_on_pix"]


def test_order_timeline_is_the_measured_seven_events() -> None:
    timeline = contract_v2()["verification"]["timeline"]
    values = [event["value"] for event in timeline["events"]]
    assert values == [
        "CREATED",
        "PLACED",
        "CONFIRMED",
        "DELIVERY_REQUEST_CREATED",
        "ENABLE_TIP",
        "DELIVERY_CREATED",
        "DELIVERY_REQUEST_IN_PROGRESS",
    ]
    assert "-03:00" in timeline["timezone_wart"]
    assert timeline["eta_fields"] == ["deliversAt", "deliversEndAt"]
    assert timeline["final_state"]["last_status"] == "CONFIRMED"


def test_payment_is_marked_by_created_to_placed_not_by_an_event() -> None:
    """Não existe PAYMENT_APPROVED: quem marca pagamento é a transição CREATED→PLACED."""
    timeline = contract_v2()["verification"]["timeline"]
    values = {event["value"] for event in timeline["events"]}
    assert "PAYMENT_APPROVED" not in values
    assert "PLACED" in values
    assert timeline["payment_marker"] == "CREATED → PLACED marca pagamento aprovado"
    assert "nunca passa" in timeline["no_payment_event"]


def test_confirmed_is_store_acceptance_not_payment() -> None:
    """Estados vizinhos no tempo, semânticas diferentes: 1 s aqui, pode ser muito lá."""
    timeline = contract_v2()["verification"]["timeline"]
    assert "NÃO é pagamento" in next(
        event["means"] for event in timeline["events"] if event["value"] == "CONFIRMED"
    )
    assert "aceite da loja" in timeline["confirmed_is_not_payment"]


def test_payments_object_has_no_status_field() -> None:
    """Status de pagamento só se infere pela timeline — não existe campo."""
    timeline = contract_v2()["verification"]["timeline"]
    assert "não tem campo de status" in timeline["payments_has_no_status"]


def test_both_created_and_confirmed_appear_in_the_same_capture() -> None:
    """A armadilha: escolher o snapshot errado faz ler pedido pago como pendente."""
    timeline = contract_v2()["verification"]["timeline"]
    values = [event["value"] for event in timeline["events"]]
    assert values[0] == "CREATED" and "CONFIRMED" in values
    assert timeline["final_state"]["payment"].startswith("Pix pago")


def test_session_degrades_in_minutes_but_is_not_a_ttl() -> None:
    """Não é TTL: é degradação observada. Nome errado induz refresh que piora o score."""
    from support.pending.web_paths import SESSION_DEGRADES_AFTER_MINUTES

    session = contract_v2()["session"]
    assert session["ttl_unit"].startswith("minutos")
    assert SESSION_DEGRADES_AFTER_MINUTES == 5
    assert "não" in session["not_a_ttl"]
    assert "sidecar" in session["consequence"]


def test_the_three_checkout_headers_are_the_measured_ones() -> None:
    headers = contract()["required_headers"]
    assert tuple(headers) == CHECKOUT_HEADERS
    assert set(CHECKOUT_HEADERS) == {
        "X-Ifood-Device-Id",
        "X-Ifood-Device-Payment-Secret",
        "X-Ifood-Customer-Id",
    }


def test_payment_secret_is_the_cookie_value_without_transformation() -> None:
    """C11 caiu: o header recebe o valor do cookie direto, não um hash."""
    secret = contract()["required_headers"]["X-Ifood-Device-Payment-Secret"]
    assert secret["source"].startswith("cookie x-ifood-device-payment-")
    assert "direto" in secret["source"]
    assert "getCookie" in secret["detail"]
    assert CHECKOUT_INTEGRITY["device_secret_source"].startswith("cookie x-ifood-device-payment-")
    assert CHECKOUT_INTEGRITY["confidence"]["cart_response_field"] == "medido-no-bundle"


def test_cart_response_and_validation_version_are_opaque() -> None:
    """Nada de derivar nem recalcular: guardar inteiro e repassar."""
    payload = contract()["payload"]
    assert payload["cartResponse"]["treatment"].startswith("opaco")
    assert payload["validationVersion"]["treatment"].startswith("string opaca")
    assert payload["cartResponse"]["origin"] == "resposta do carrinho, assinada pelo servidor"


def test_attempt_purchase_is_inferred_not_contract() -> None:
    """Idempotência é o teste mais perigoso do projeto: aqui só o rótulo."""
    attempt = contract()["payload"]["attemptPurchase"]
    assert attempt["confidence"] == "inferido"
    assert "NÃO medido" in attempt["idempotency"]
    assert CHECKOUT_INTEGRITY["attempt_purchase"].endswith("NÃO medida")


def test_missing_cart_read_is_declared_missing() -> None:
    """Não existe GET de carrinho: declarar ausência evita inventar rota."""
    unknown = contract()["unknowns"]["cart_read"]
    assert unknown["status"] == "nao-medido"
    assert "não existe GET" in unknown["note"]


def test_no_auto_retry_on_purchase() -> None:
    """Política do projeto: POST de compra nunca repete sozinho."""
    policy = contract()["policy"]
    assert policy["no_auto_retry_on_purchase"] is True
    assert "estado desconhecido" in policy["reason"]


def test_garnish_is_resolved_as_not_part_of_v2() -> None:
    """Duas variantes, ambas deram ITEM-001: não eleger vencedora sem cassete."""
    garnish = contract()["garnish"]
    assert garnish["status"] == "resolvido-na-v2"
    assert "subItems" in garnish["note"]
    assert len(garnish["variants"]) == 2
    assert len(GARNISH_VARIANTS) == 2
    assert {variant["status"] for variant in GARNISH_VARIANTS} == {"descartado-na-v2"}
    assert [tuple(v["keys"]) for v in GARNISH_VARIANTS] == [
        tuple(garnish["variants"][0]["keys"]),
        tuple(garnish["variants"][1]["keys"]),
    ]
    assert "choiceCode" in garnish["trap"]
    assert garnish["v1"]["wire_shape"] == "nao-medido", "a forma da v1 segue sem captura"


def test_writing_is_edge_gated_but_reading_is_not() -> None:
    """Método muda a regra da borda: POST leva 403 mesmo com jar novo."""
    from support.pending.web_paths import WRITE_REQUIRES_BROWSER_ORIGIN

    gate = contract()["write_gate"]
    assert gate["reading"] == "livre"
    assert "browser" in gate["writing"]
    assert gate["observed"].startswith("403 cf-mitigated")
    assert "httpx" in gate["clients_tested"]
    assert gate["observed"].startswith(str(WRITE_REQUIRES_BROWSER_ORIGIN["observed"]))
    assert "sidecar" in str(WRITE_REQUIRES_BROWSER_ORIGIN["consequence"])


@pytest.mark.skipif(not JAR.exists(), reason="jar da sessão não está nesta máquina")
def test_session_can_build_the_checkout_headers_from_the_jar() -> None:
    """Se o jar tem os três cookies, o checkout é possível fora do browser."""
    session = Session(client=None, cookies=read_jar(JAR), path=JAR)  # type: ignore[arg-type]
    headers = session.checkout_headers
    assert set(headers) == set(CHECKOUT_HEADERS), session.missing_checkout_headers()
    assert session.has_payment_secret is True


# checkout real (v2)
V2 = FIXTURE.parent / "checkout_v2_contract.json"


def v2() -> dict:
    return json.loads(V2.read_text(encoding="utf-8"))


def test_checkout_is_the_cart_bff_route_not_wsloja() -> None:
    """Medido no pedido real: o web atual finaliza em ``/v2/carts/{id}/checkout``."""
    from support.pending.web_paths import CHECKOUT_ROUTES

    facts = v2()
    from support.pending.web_paths import bff_path

    endpoint = facts["checkout"]["endpoint"]
    assert endpoint["path"] == "/site-api/v2/carts/{cartId}/checkout"
    assert bff_path("/v2/carts/{cartId}/checkout") == endpoint["path"]
    assert facts["checkout"]["status"] == 201
    declared = {route.name: route for route in CHECKOUT_ROUTES}
    assert declared["cart_checkout"].confidence == "capturado"
    assert "wsloja" in declared["checkout_wsv3"].note
    assert "NÃO usada" in declared["checkout_wsv3"].note


def test_checkout_body_is_cart_request_string_plus_payment_sources() -> None:
    facts = v2()["checkout"]
    shape = facts["body_shape"]
    assert set(shape) == {"cartRequest", "cpfCnpj", "signature", "paymentSources"}
    assert shape["cartRequest"].startswith("string"), "cartRequest vai SERIALIZADO, não objeto"
    assert facts["cartRequest_inner"]["keys"] == ["cartResponse", "signature"]
    assert {"source", "amount", "paymentMethod"} <= set(shape["paymentSources"]["sources"][0])


def test_checkout_has_no_idempotency_field() -> None:
    """O que não existe também é contrato: nada de assumir idempotência."""
    absent = set(v2()["checkout"]["absent_fields"])
    assert {"attemptPurchase", "validationVersion"} <= absent
    assert CHECKOUT_INTEGRITY["attempt_purchase"].endswith("NÃO medida")


def test_snapshot_lease_is_ten_seconds_after_the_last_mutation() -> None:
    """expiresAt = última mutação + ~10,3 s; o web finalizou 0,40 s depois de mutar."""
    lease = v2()["snapshot_lease"]
    assert lease["measured"]["last_mutation"] == "03:36:38.813Z (PUT deliveryMethod)"
    assert lease["measured"]["checkout_sent"].endswith("(+0.40s)")
    assert lease["measured"]["snapshot_expiresAt"].endswith("(+10.31s)")
    assert "intencao" in lease["consequence"].replace("ç", "c")


def test_order_verification_polls_events_and_reads_pix_from_the_order() -> None:
    """A tela de "pagamento pendente" confirma por detalhe + eventos, a cada ~5 s."""
    from support.pending.web_paths import VERIFICATION_ROUTES

    facts = v2()["verification"]
    from support.pending.web_paths import bff_path

    assert facts["order_events"]["path"] == bff_path("/v1/customers/me/orders/{orderId}/events")
    assert "5 s" in facts["order_events"]["polling"]
    assert facts["order_status_at_creation"] == "CREATED"
    assert "pix.qrCode" in facts["pix_qr_also_in_order"]
    assert facts["delivery_code"]["name"] == "DELIVERY_CODE"
    paths = [route.path for route in VERIFICATION_ROUTES]
    assert "/v3/customers/me/orders/{orderId}" in paths
    assert "/v1/customers/me/orders/{orderId}/events" in paths


def test_delivery_code_is_optional_and_has_a_purpose() -> None:
    code = v2()["verification"]["delivery_code"]
    assert code["required"] is False
    assert code["source"] == "account-delivery-code"
    assert "entregador" in code["purpose"]
    assert "não bloqueia" in code["does_not_block"]


def test_real_checkout_file_from_report_matches_the_lib_shape() -> None:
    """Comparação contra o arquivo real salvo em ``report/`` (não só o cassete)."""
    real_file = FIXTURE.parent / "checkout_v2_request.json"
    if not real_file.exists():
        pytest.skip("checkout_v2_request.json não está nesta cópia")
    real = json.loads(real_file.read_text(encoding="utf-8"))
    assert set(real) == {"cartRequest", "cpfCnpj", "paymentSources", "signature"}
    assert isinstance(real["cartRequest"], str), "cartRequest é string, não objeto"
    inner = json.loads(real["cartRequest"])
    assert set(inner) == {"cartResponse", "signature"}
    assert real["signature"] == inner["signature"], "a assinatura do topo é a do carrinho"
    source = real["paymentSources"]["sources"][0]
    assert set(source) >= {"source", "amount", "paymentMethod"}
    assert source["paymentMethod"]["name"] == "PIX"


# redação do checkout
def test_cpf_signature_and_pix_code_are_never_stored() -> None:
    from support.pending.http import redact_json

    payload = {
        "cpfCnpj": "100.448.904-86",
        "signature": "MEUCIAtVecV+tJyqId4FrF1+QH/N9w5sdZdAZ3iS" + "x" * 52,
        "pixQRCode": "00020101021226900014br.gov.bcb.pix2568pix.adyen.com",
        "orderId": "0fb5ae11-e079-4809-b777-a157ae37a95a",
    }
    redacted = redact_json("", payload)
    assert isinstance(redacted, dict)
    for key in ("cpfCnpj", "signature", "pixQRCode", "orderId"):
        assert redacted[key] == "<redacted>", f"{key} não foi redigido"


def test_email_hidden_in_a_fingerprint_value_is_redacted() -> None:
    """Medido: ``cybersourceFingerprint`` vinha com o e-mail colado em dígitos."""
    from support.pending.http import looks_like_email, redact_json

    assert looks_like_email("ALGUEM@EXEMPLO.COM211")
    redacted = redact_json("", {"cybersourceFingerprint": "ALGUEM@EXEMPLO.COM211"})
    assert isinstance(redacted, dict)
    assert redacted["cybersourceFingerprint"] == "<redacted>"


def test_nested_json_string_is_redacted_not_stored_raw() -> None:
    """``cartRequest`` é 25 KB de JSON dentro de string: não pode passar cru."""
    from support.pending.http import redact_json

    nested = json.dumps({"cartResponse": {"account": {"email": "a@b.com"}}, "signature": "x" * 96})
    redacted = redact_json("", {"cartRequest": nested})
    assert isinstance(redacted, dict)
    stored = redacted["cartRequest"]
    assert isinstance(stored, str)
    assert "a@b.com" not in stored
    assert "x" * 96 not in stored
    assert "<redacted>" in stored
