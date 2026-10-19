"""Fumaça por endpoint com o jar da sessão do operador.

Desenho decidido (medido pelo ifood-api, aceito aqui):

- o **jar de sessão é artefato de primeira classe**; o browser só faz o bootstrap
  de borda (Cloudflare + PerimeterX); o resto roda em HTTP puro;
- a fumaça é **por endpoint, nunca por TTL único**: o `_px3` vale para
  `/v2/categories` e não vale para `/v1/merchants/restaurant/{uuid}/catalog` na
  mesma janela;
- 403 de PX **não é falha de contrato** (regra R0): o teste pula dizendo qual
  endpoint está barrado, em vez de afirmar 403;
- nada aqui grava cassete: `--record` é proibido neste arquivo, o cassete de
  sessão real nasce do `measure.py` (com redação), não da suíte.

Uso:

    uv run pytest tests/test_smoke_session.py --live --jar ~/session.jar -v
"""

import json
import time
from typing import TYPE_CHECKING

import pytest
from support.pending.errors import IfoodApiError

if TYPE_CHECKING:
    from support.pending.session import Session

pytestmark = [pytest.mark.live, pytest.mark.session]

BASE = "https://www.ifood.com.br"


def _request(session: Session, method: str, path: str, params: dict | None):
    return session.client.request(
        method,
        BASE + path,
        headers=session.headers,
        params=params,
    )


def _call(session: Session, method: str, path: str, **kwargs: object):
    """Executa e classifica: devolve a resposta ou pula em barreira de borda.

    Um retry só, em 403 de borda: o ``cf_clearance`` oscila (medido pelo ifood-api:
    403 "Just a moment" e 200 na chamada seguinte, mesmo jar). Sem isso a suíte
    reportaria sessão morta por ruído de borda.
    """
    params = kwargs.get("params")
    response = _request(session, method, path, params if isinstance(params, dict) else None)
    if response.status_code == 403 and "just a moment" in response.text[:2000].lower():
        time.sleep(2.0)
        response = _request(session, method, path, params if isinstance(params, dict) else None)
    if response.status_code in {403, 429}:
        error = IfoodApiError.from_response(
            response.status_code, path, response.text, response_headers=dict(response.headers)
        )
        pytest.skip(
            f"barreira de borda em {path} ({response.status_code} "
            f"{error.envelope if error else '?'}) — não é contrato.\n{session.describe()}"
        )
    return response


def _json(response):
    try:
        return json.loads(response.text)
    except ValueError:
        return None


def test_jar_has_a_user_session(session: Session) -> None:
    """Sem os dois tokens da conta o jar é só borda: fumaça autenticada não roda."""
    assert session.has_user_session, (
        "jar sem aAccessToken/aRefreshToken: refaça o login no browser.\n" + session.describe()
    )


def test_customers_me(session: Session) -> None:
    response = _call(session, "GET", "/site-api/v1/customers/me")
    assert response.status_code == 200, response.text[:300]
    payload = _json(response)
    assert isinstance(payload, dict)


def test_orders_list_is_the_base_of_reorder(session: Session) -> None:
    """``/v4/customers/me/orders`` é a base do "repetir pedido"."""
    response = _call(
        session, "GET", "/site-api/v4/customers/me/orders", params={"page": 0, "size": 10}
    )
    assert response.status_code == 200, response.text[:300]
    payload = _json(response)
    assert isinstance(payload, (list, dict)), "esperava lista de pedidos ou envelope com ela"


def test_addresses(session: Session) -> None:
    response = _call(session, "GET", "/site-api/v1/customers/me/addresses")
    assert response.status_code == 200, response.text[:300]


def test_reorder_requires_coordinates(session: Session) -> None:
    """Sem ``lat``/``lon`` o reorder recusa com ``SCO-3000`` — erro de negócio, não borda."""
    response = _call(
        session,
        "GET",
        "/site-api/v1/customers/me/orders/00000000-0000-4000-8000-000000000000/reorder",
    )
    error = IfoodApiError.from_response(
        response.status_code, "reorder", response.text, response_headers=dict(response.headers)
    )
    assert error is not None, "reorder sem coordenadas deveria recusar"
    assert error.code == "SCO-3000", f"código inesperado: {error.code} ({error.envelope})"


def test_reorder_with_coordinates_from_a_real_order(session: Session) -> None:
    """Cadeia real: pega um pedido da lista e pede o reorder com coordenadas."""
    listing = _call(
        session, "GET", "/site-api/v4/customers/me/orders", params={"page": 0, "size": 1}
    )
    payload = _json(listing)
    orders = payload if isinstance(payload, list) else (payload or {}).get("orders") or []
    if not orders:
        pytest.skip(
            "sem pedido na conta: o fluxo de reorder não pode ser exercitado (é dado, não contrato)"
        )
    order_id = orders[0].get("id") if isinstance(orders[0], dict) else None
    assert order_id, "pedido sem id na listagem"

    response = _call(
        session,
        "GET",
        f"/site-api/v1/customers/me/orders/{order_id}/reorder",
        params={"lat": -23.5613, "lon": -46.6565},
    )
    assert response.status_code == 200, response.text[:300]
    reordered = _json(response)
    assert isinstance(reordered, dict)
    for key in ("merchant", "bag", "deliveryMethod"):
        assert key in reordered, f"reorder sem `{key}`"
    bag = reordered["bag"]
    assert isinstance(bag, dict) and "items" in bag


def test_px_gated_menu_is_skipped_not_failed(session: Session) -> None:
    """Menu é o caso onde o PX morre mesmo com jar: pular é o comportamento certo."""
    response = _call(
        session,
        "GET",
        "/site-api/v1/merchants/restaurant/0dfcf629-0000-4000-8000-000000000000/catalog",
        params={"latitude": -23.5613, "longitude": -46.6565},
    )
    # Se passou, ótimo: o PX liberou para este path. Se não, _call já pulou.
    assert response.status_code in {200, 400, 404}, response.text[:200]


def test_cart_write_is_edge_gated_not_business(session: Session) -> None:
    """Corpo inválido de propósito: não cria carrinho, só revela quem barra.

    Medido pelo ifood-api: POST leva ``403 cf-mitigated: challenge`` mesmo com jar
    novo, em httpx e em curl_cffi. Aqui a asserção aceita 403 (borda) ou 400 (regra),
    e **nunca** 201 — porque criar carrinho não é efeito colateral aceitável de teste.
    """
    response = session.client.post(BASE + "/site-api/v2/carts", headers=session.headers, json={})
    assert response.status_code != 201, "corpo vazio não deveria criar carrinho"
    if response.status_code == 403:
        assert "just a moment" in response.text[:2000].lower() or response.headers.get(
            "cf-mitigated"
        ), "403 sem marca de borda: revisar a leitura de escrita"
        pytest.skip("escrita barrada pela borda (esperado): fumaça de escrita exige browser")
    assert response.status_code == 400, response.text[:200]
