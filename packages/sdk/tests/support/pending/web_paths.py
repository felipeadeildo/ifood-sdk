"""Rotas de identidade do **web app**, extraídas do bundle e ainda não capturadas.

Fonte: `web/full/_app-6a5d151cf7ebe925.js` (5,4 MB, bundle de produção servido por
`www.ifood.com.br`), módulos `39702` (constantes), `46645` (serviço de conta) e o
componente de desafios (`account-challenges.ifood.com.br`).

O que isto resolve: `ifood-api` perguntou qual par o web usa — `oauth/token` com
PKCE ou `/v2/access_tokens` + `/v1/challenges`. A resposta observada no bundle é a
segunda: **não há `oauth/token`, não há `code_challenge`, não há `authorize`** no
web app. O login é `email + password` e o OTP tem cadeia própria.

Base URL: o serviço de conta usa a instância `J = U(42455)`, que é a de
`EXTERNAL_MARKETPLACE_URL` → `https://www.ifood.com.br/site-api/`. Ou seja, as
rotas abaixo são **same-origin no BFF**, não em `consumer-api` nem em `id.ifood`.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebRoute:
    """Uma rota observada no bundle. ``confidence`` diz o quanto já foi provado."""

    name: str
    method: str
    path: str
    body_keys: tuple[str, ...] = ()
    confidence: str = "observado-no-bundle"
    host: str = "www"
    note: str = ""


#: Login e token. Sem OAuth2/PKCE: é o mesmo desenho do app (dex).
IDENTITY_ROUTES: tuple[WebRoute, ...] = (
    # Confirmadas na captura `evidence/login-01` (2026-10-19T03:11Z). O login do
    # web é **OTP sem senha**: não há grant de senha, não há PKCE, não há
    # `/oauth/token`. A versão do path importa — `/identity-providers/IFOOD/
    # authentications` (sem versão), que eu tinha lido no bundle, não existe.
    WebRoute(
        "identity_providers",
        "POST",
        "/v4/identity-providers",
        note="lista provedores do tenant; com {tenant_id,email} devolve conta/telefone",
        confidence="capturado",
    ),
    WebRoute(
        "otp_authorization_code",
        "POST",
        "/v2/identity-providers/OTP/authorization-codes",
        note="envia o OTP: 201 {key, timeout_in_seconds:60}; key é de uso único",
        confidence="capturado",
    ),
    WebRoute(
        "otp_access_token",
        "POST",
        "/v2/identity-providers/OTP/access-tokens",
        note="201 {access_token} — token de challenge, não é o JWT",
        confidence="capturado",
    ),
    WebRoute(
        "otp_challenge_confirm",
        "POST",
        "/v1/identity-providers/OTP/challenges",
        note="200 {email} mascarado; confirma o destino",
        confidence="capturado",
    ),
    WebRoute(
        "otp_authenticate",
        "POST",
        "/v3/identity-providers/OTP/authentications",
        note="201 JWT + refresh + account_id; corpo {tenant_id,token,device_id,email}",
        confidence="capturado",
    ),
    WebRoute(
        "oauth_token",
        "POST",
        "/oauth/token",
        note="NÃO usada pelo web: nenhuma ocorrência no bundle nem nas 4 capturas de login",
        confidence="descartado",
        host="id",
    ),
)

CUSTOMER_ROUTES: tuple[WebRoute, ...] = (
    WebRoute("customers_me", "GET", "/v1/customers/me", note="conta + user-order-attributes"),
    WebRoute("customers_me_account", "GET", "/v1/customers/me/account"),
    WebRoute("addresses", "GET", "/v1/customers/me/addresses"),
    WebRoute(
        "card_tokens",
        "GET",
        "/v1/customers/me/card-tokens",
        note="cartões salvos (PAN nunca no browser)",
    ),
    WebRoute("orders_received", "GET", "/v1/customers/me/orders:received"),
    WebRoute("contact_methods", "GET", "/v1/customers/me/contact-methods"),
    WebRoute("loyalty_cards", "GET", "/v1/customers/me/loyalty-cards"),
    WebRoute("place_list", "GET", "/customer/place/list"),
    WebRoute("place_favorite", "POST", "/customer/place/favorite"),
)

#: Host do componente de desafio (MFA) — vem do próprio bundle, não do dex.
ACCOUNT_CHALLENGES_HOST = "https://account-challenges.ifood.com.br"
ACCOUNT_CHALLENGES_KEYS = ("challenges", "authContextId", "authScope", "requiresAccessToken")

#: Como o web trata token expirado (módulo 46645): decodifica `exp` no cliente e
#: reautentica antes de usar. O `reAuthenticate` tenta 3 vezes e distingue
#: "sem refresh token", 401 e falha de rede.
REAUTH_MAX_ATTEMPTS = 3
REAUTH_FAILURES = (
    "No JWT refresh token",
    "No access token in marketplace response",
    "Network Error",
)


def paths() -> dict[str, str]:
    """``nome → path`` para quem só quer montar URL."""
    return {
        route.name: route.path
        for route in IDENTITY_ROUTES + CUSTOMER_ROUTES + CHECKOUT_ROUTES + REORDER_ROUTES
        if route.confidence != "descartado"
    }


@dataclass(frozen=True, slots=True)
class CartRoute:
    """Rota do carrinho. ``path`` usa ``{base}`` = ``/v1/carts`` **ou** ``/v2/carts``.

    O web escolhe por flag remota ``cartApiV2Enabled`` (módulo 47707): v1 vai para
    ``wsloja.ifood.com.br/ifood-ws-v3`` com ``access_key``/``secret_key`` estáticas;
    v2 vai para o BFF ``www/site-api``. O cliente tem que suportar as duas.
    """

    name: str
    method: str
    path: str
    note: str = ""


CART_BASES = ("/v1/carts", "/v2/carts")

#: Convenção deste módulo: ``path`` das rotas é relativo ao **prefixo BFF**
#: ``/site-api`` (as do web app). Rotas de outro host (WSV3) vêm com o path inteiro.
BFF_PREFIX = "/site-api"


def bff_path(path: str) -> str:
    """Caminho com o prefixo BFF: ``bff_path("/v2/carts")`` → ``/site-api/v2/carts``."""
    return f"{BFF_PREFIX}{path}"


def bff_url(path: str, host: str = "https://www.ifood.com.br") -> str:
    """Igual a :func:`bff_path`, mas com host — pronto para chamar."""
    return f"{host}{bff_path(path)}"


CART_ROUTES: tuple[CartRoute, ...] = (
    CartRoute(
        "create_cart",
        "POST",
        "{base}",
        "escrita: depende de sessão originada no browser (ver WRITE_REQUIRES_BROWSER_ORIGIN); "
        "payload mínimo em CART_CREATE_PAYLOAD, recusa por código (CART_VALIDATION_CHAIN)",
    ),
    CartRoute("create_cart_items", "POST", "{base}/{cartId}/items"),
    CartRoute("edit_cart_item", "PUT", "{base}/{cartId}/items/{cartItemId}"),
    CartRoute("delete_cart_item", "DELETE", "{base}/{cartId}/items/{cartItemId}"),
    CartRoute("update_delivery_method", "PUT", "{base}/{cartId}/deliveryMethod"),
    CartRoute(
        "update_payment_method",
        "PUT",
        "{base}/{cartId}/paymentMethod",
        "corpo é lista: [paymentMethod]",
    ),
    CartRoute("update_address", "PUT", "{base}/{cartId}/address"),
    CartRoute("update_voucher", "PUT", "{base}/{cartId}/voucher"),
    CartRoute("delete_voucher", "DELETE", "{base}/{cartId}/voucher"),
    # Curiosidade do próprio web app: esta ignora a flag e bate sempre em /v1.
    CartRoute("delete_cart", "DELETE", "/v1/carts/{cartId}", "hardcoded em /v1 no bundle"),
)

#: Ordem de validação do `POST {base}`, medida pelo ifood-api: cada passo recusa com
#: um código distinto, então o código funciona como bússola para montar o payload.
CART_VALIDATION_CHAIN: tuple[tuple[str, str, str], ...] = (
    ("CART-006", "merchant", "campo obrigatório"),
    ("CART-007", "merchant", "precisa objeto {id}, não id solto"),
    ("CART-006", "address", "precisa o objeto inteiro vindo de /v1/customers/me/addresses"),
    ("CART-006", "items", "lista; cada item precisa `id`"),
    ("CART-006", "id", "id do item"),
    ("CART-006", "delivery", "objeto de entrega"),
    ("CART-007", "now", 'precisa a string "true", não boolean'),
    ("ITEM-001", "garnish", "complementos obrigatórios faltando"),
)

#: Payload que passou da validação (até bater em ITEM-001 por complemento).
CART_CREATE_PAYLOAD = {
    "merchant": {"id": "<uuid>"},
    "address": "<objeto inteiro de /v1/customers/me/addresses>",
    "items": [{"id": "<uuid>", "quantity": 1, "garnish": "<opcional>"}],
    "delivery": {"id": "DEFAULT", "mode": "DELIVERY", "now": "true"},
}

#: Headers que o checkout do web exige (módulo ~4205k). `deviceSecret` vem de cookie.
CHECKOUT_HEADERS = ("X-Ifood-Device-Id", "X-Ifood-Device-Payment-Secret", "X-Ifood-Customer-Id")
CHECKOUT_ROUTES: tuple[WebRoute, ...] = (
    WebRoute(
        "cart_checkout",
        "POST",
        "/v2/carts/{cartId}/checkout",
        confidence="capturado",
        note=(
            "o checkout do web ATUAL: BFF, 201 {orderId, pixQRCode, cartResponse}. "
            "Corpo {cartRequest(string JSON), cpfCnpj, signature, paymentSources}. "
            "Não tem attemptPurchase/validationVersion"
        ),
    ),
    WebRoute(
        "checkout_wsv3",
        "POST",
        "/v6/order/checkout",
        confidence="observado-no-bundle",
        note=(
            "wsloja/ifood-ws-v3: presente no bundle, NÃO usada pelo web atual "
            "(nenhuma request a wsloja nas capturas). Tratar como legado até ver na rede"
        ),
    ),
    WebRoute(
        "delivery_fee",
        "POST",
        "/v6/order/deliveryfee",
        confidence="observado-no-bundle",
        note="recalcula frete; chamado antes do checkout",
    ),
    WebRoute(
        "card_verification",
        "POST",
        "/v1/card-verifications",
        confidence="observado-no-bundle",
        note="BFF; valida cartão novo antes de salvar",
    ),
)

#: Integridade de preço: o web manda o *carrinho assinado* junto do checkout, então o
#: servidor rejeita payload que não veio do carrinho real. Não dá para montar checkout
#: à mão: o cliente tem que seguir o fluxo do carrinho e repassar a assinatura.
CHECKOUT_INTEGRITY = {
    # Medido (ifood-api, no bundle): o carrinho vem assinado DO SERVIDOR e o web não
    # assina nada no cliente. Tratar os dois como opaco — não derivar, não recalcular.
    "cart_response_field": "cartResponse",
    "cart_response_origin": "resposta do carrinho",
    "validation_version": "string opaca gerada no cliente por (0,s$.L)()",
    "attempt_purchase": "identificador de tentativa no payload; idempotência NÃO medida",
    "three_ds": ("braintree_threeds2_payment_method_nonce", "braintree_threeds2_payment_id"),
    "device_secret_source": "cookie x-ifood-device-payment-<sha>, valor direto (medido)",
    "confidence": {
        "cart_response_field": "medido-no-bundle",
        "validation_version": "medido-no-bundle",
        "attempt_purchase": "inferido",
        "old_price_revalidation": "nao-medido",
    },
}

#: Variantes de `garnish` vistas no código, **descartadas na v2**: o item usa
#: `subItems[{id, quantity}]` e `observation` é a observação. O `ITEM-001` que as duas
#: variantes produziam era por mandar `garnish` onde o endpoint espera `subItems`.
#: Ficam registradas para a v1 (WSV3), onde `garnish` é o nome de campo do bundle e
#: cuja forma no wire segue **não medida**.
GARNISH_VARIANTS: tuple[dict[str, object], ...] = (
    {
        "shape": "plano",
        "keys": ("parentCode", "code", "name", "amount", "unitPrice"),
        "status": "descartado-na-v2",
        "why": "v2 usa subItems; ITEM-001 vinha do campo errado, não da forma",
    },
    {
        "shape": "agrupado",
        "keys": ("code", "garnishItens"),
        "item_keys": ("code", "description", "qty", "unitPrice"),
        "status": "descartado-na-v2",
        "why": "idem: o endpoint v2 não tem `garnish`",
    },
)

#: Escrita x leitura na borda: **o método muda a regra**. Medido pelo ifood-api:
#: com jar antigo o POST chegava na regra (CART-006); com jar novo, POST v1 e v2
#: devolvem 403 `cf-mitigated: challenge` em httpx **e** em curl_cffi chrome/131.
#: Leitura segue livre; escrita exige sessão originada no browser.
WRITE_REQUIRES_BROWSER_ORIGIN: dict[str, object] = {
    "applies_to": ("POST", "PUT", "PATCH", "DELETE"),
    "observed": "403 cf-mitigated: challenge",
    "clients_tested": ("httpx", "curl_cffi chrome", "curl_cffi chrome131"),
    "reading": "leitura livre; escrita depende de sessão/TLS nascida no browser",
    "status": "estado do projeto, não limitação temporária",
    "why_not_a_signature": (
        "a porta móvel não é HMAC com chave embutida: o APK carrega Play Integrity "
        "(IntegrityToken / IntegrityManager / IntegrityTokenRequest), ou seja, atestação "
        "de aparelho. Não há 'uma assinatura' a descobrir."
    ),
    "consequence": (
        "nenhum teste de escrita pode se dizer offline ou determinístico; o MCP precisa de "
        "sidecar com browser para qualquer verbo de escrita"
    ),
}

#: Medido pelo ifood-api em 2026-10-19, tudo HTTP puro (com jar de sessão).
#: ``confidence="capturado"``: o corpo/status foi visto, não deduzido do bundle.
REORDER_ROUTES: tuple[WebRoute, ...] = (
    WebRoute(
        "orders_list",
        "GET",
        "/v4/customers/me/orders",
        body_keys=("page", "size"),
        confidence="capturado",
        note="10 pedidos, ~93 KB; traz delivery.address, merchant, payments e bag",
    ),
    WebRoute(
        "order_reorder",
        "GET",
        "/v1/customers/me/orders/{orderId}/reorder",
        body_keys=("lat", "lon"),
        confidence="capturado",
        note="sem lat/lon recusa 400 SCO-3000; com eles devolve merchant+bag prontos",
    ),
)

#: Envelopes de erro: três famílias, cada uma com seu leitor. O cliente que só lê
#: ``body["code"]`` perde CART/ITEM/SCO e vira "erro desconhecido".
ERROR_ENVELOPES = {
    "flat": {"code", "message", "details"},
    "nested": {"error": {"code", "message"}},
    "kong": {"message"},
}

#: Headers obrigatórios nas rotas de identidade, medidos pelo ifood-api: o corpo
#: exato com um destes ausente vira ``400 OTP-2000 "Illegal Argument"``. Ou seja,
#: **passa pela borda e falha na regra** — não confundir com cookie vencido.
IDENTITY_REQUIRED_HEADERS: tuple[str, ...] = (
    "app_name",
    "app_version",
    "platform",
    "country",
    "x-client-application-key",
    "x-ifood-session-id",
    "x-ifood-device-id",
    "x-device-model",
    "browser",
)

#: Rotas do OTP cujo corpo foi confirmado; ``email`` não está aqui porque falhou nos
#: dois formatos tentados e o shape certo é **desconhecido** (não presumir simetria).
OTP_PHONE_BODY_KEYS: tuple[str, ...] = ("tenant_id", "type", "phone")
OTP_ACCESS_TOKEN_BODY_KEYS: tuple[str, ...] = ("key", "auth_code")

#: Como o web confirma que o pedido existe e como o pagamento está caminhando.
VERIFICATION_ROUTES: tuple[WebRoute, ...] = (
    WebRoute(
        "order_detail",
        "GET",
        "/v3/customers/me/orders/{orderId}",
        confidence="capturado",
        note="traz lastStatus, payments[].pix.qrCode, verificationCodes[].value (código de entrega)",
    ),
    WebRoute(
        "order_events",
        "GET",
        "/v1/customers/me/orders/{orderId}/events",
        confidence="capturado",
        note="a tela de pagamento pendente faz polling a cada ~5 s",
    ),
)

#: Regra medida do snapshot: expiresAt = última mutação do carrinho + ~10 s.
SNAPSHOT_LEASE_SECONDS = 10.31

#: Observação, **não** TTL contratual: a sessão colhida do browser **degradou** ~5 min
#: depois de muito tráfego automatizado — não "expirou em 5 min". O `expiresAt` do
#: `cf_clearance` continuava longo; o que caiu foi a pontuação de bot. Nomear como
#: TTL convidaria a um refresh a cada 5 min, que piora o score ainda mais rápido.
SESSION_DEGRADES_AFTER_MINUTES = 5
