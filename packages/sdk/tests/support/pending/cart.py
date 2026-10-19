"""Carrinho: payload das **duas** versões da API, e a leitura da resposta.

O que a captura ``cart-01`` (operador adicionando item, 2026-10-19) mostrou é que o
mesmo carrinho tem dois contratos incompatíveis, e a diferença não é cosmética:

- **v2** (`POST /site-api/v2/carts`, BFF, o que o web usa hoje): complementos vão em
  ``items[].subItems[]`` com ``id`` e ``quantity``; ``delivery.now`` é **boolean**;
  não existe ``mode``; e o corpo carrega ``account`` (id/nome/e-mail/telefone) e
  ``source`` (nome/plataforma/requisitante/versão).
- **v1** (`POST /wsloja/ifood-ws-v3/v1/carts`, WSV3): complementos vão em
  ``items[].garnish``; ``delivery.now`` tem que ser a **string** ``"true"``
  (boolean dá ``CART-007``); e existe ``delivery.mode``.

Mandar um pelo outro não é erro de estilo: é ``CART-007`` no servidor. Por isso a
versão é parâmetro obrigatório aqui, não default silencioso.

A resposta 201 do v2 é ``{cartResponse, signature, data, warning}``: ``cartResponse``
é o carrinho assinado (o que o checkout consome) e ``data`` é a visão renderizada
(servidores de preço, métodos de entrega). ``cartResponse.expiresAt`` é ~10 s depois
de ``createdAt`` e cada avaliador tem o próprio vencimento — é o que impede "mostrar
o preço, esperar o humano aprovar e só então finalizar".
"""

from dataclasses import dataclass, field
from typing import Final, Literal

from .web_paths import CART_VALIDATION_CHAIN

CartVersion = Literal["v1", "v2"]

CART_MISSING: Final = "CART-006"
CART_WRONG_TYPE: Final = "CART-007"
ITEM_MISSING_GARNISH: Final = "ITEM-001"

#: Campos de topo obrigatórios, na ordem em que o servidor os valida (cadeia medida).
_REQUIRED_TOP_LEVEL: Final = ("merchant", "address", "items", "delivery")
_CHAIN_FIELDS: Final = [field_name for _code, field_name, _note in CART_VALIDATION_CHAIN]


def _top_level_order(chain_fields: list[str]) -> list[str]:
    order: list[str] = []
    for name in chain_fields:
        if name in _REQUIRED_TOP_LEVEL and name not in order:
            order.append(name)
    return order


if _top_level_order(_CHAIN_FIELDS) != list(_REQUIRED_TOP_LEVEL):
    raise AssertionError("ordem de validação do carrinho divergiu da cadeia medida")


class CartPayloadError(ValueError):
    """Payload recusável antes de sair da máquina, com o código da API."""

    def __init__(self, code: str, field_name: str, detail: str) -> None:
        self.code = code
        self.field = field_name
        self.detail = detail
        super().__init__(f"{code} campo `{field_name}`: {detail}")


@dataclass(frozen=True, slots=True)
class SubItem:
    """Complemento na v2: um id do catálogo e a quantidade escolhida."""

    id: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class CartItem:
    """Item do carrinho.

    ``sub_items`` só vale na v2; ``garnish`` só na v1. O validador recusa o campo da
    versão errada, porque o servidor também recusa — só que com erro genérico.
    """

    id: str
    quantity: int = 1
    observation: str | None = None
    sub_items: tuple[SubItem, ...] = ()
    garnish: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class Account:
    """Bloco que a v2 manda no corpo. Vai **redigido** em qualquer log ou cassete."""

    id: str
    name: str
    email: str
    phone: dict[str, object]


@dataclass(frozen=True, slots=True)
class Source:
    """Proveniência do pedido. O web manda ``web/desktop/ifood`` + versão do app."""

    name: str = "web"
    platform: str = "desktop"
    requester: str = "ifood"
    version: str = "9.178.5"


@dataclass(frozen=True, slots=True)
class Delivery:
    """Entrega. ``now`` é boolean na v2 e string na v1 — é a divergência que quebra."""

    id: str = "DEFAULT"
    now: bool = True
    delivery_by: str = "IFOOD"
    mode: str = "DELIVERY"


@dataclass(frozen=True, slots=True)
class CartDraft:
    merchant_id: str
    address: dict[str, object]
    items: list[CartItem] = field(default_factory=list)
    merchant_name: str | None = None
    delivery: Delivery = field(default_factory=Delivery)
    account: Account | None = None
    source: Source = field(default_factory=Source)


def build_payload(
    draft: CartDraft, version: CartVersion = "v2", *, allow_missing_account: bool = False
) -> dict[str, object]:
    """Monta o corpo da versão pedida e valida antes de devolver.

    ``version`` não tem default silencioso por acidente: a captura mostra que o web
    usa v2, e é ela que o cliente novo deve usar. A v1 fica para o host WSV3.
    """
    if version == "v2":
        payload = _build_v2(draft)
        if draft.account is None and not allow_missing_account:
            # Medido: o corpo real sempre traz `account` e `source`; o `ifood-api`
            # reporta que o v2 os exige. A obrigatoriedade não foi testada isolada,
            # por isso a saída de emergência acima.
            raise CartPayloadError(CART_MISSING, "account", "v2 manda account no corpo")
    elif version == "v1":
        payload = _build_v1(draft)
    else:
        raise ValueError(f"versão de carrinho desconhecida: {version!r}")
    validate(payload, version=version)
    return payload


def _build_v2(draft: CartDraft) -> dict[str, object]:
    merchant: dict[str, object] = {"id": draft.merchant_id}
    if draft.merchant_name:
        merchant["name"] = draft.merchant_name

    items: list[dict[str, object]] = []
    for item in draft.items:
        entry: dict[str, object] = {"id": item.id, "quantity": item.quantity}
        entry["observation"] = item.observation or ""
        entry["subItems"] = [{"id": sub.id, "quantity": sub.quantity} for sub in item.sub_items]
        items.append(entry)

    payload: dict[str, object] = {
        "merchant": merchant,
        "address": draft.address,
        "items": items,
        "delivery": {
            "id": draft.delivery.id,
            # v2 aceita boolean (medido no corpo real: `"now": true`).
            "now": draft.delivery.now,
            "deliveryBy": draft.delivery.delivery_by,
        },
        "source": {
            "name": draft.source.name,
            "platform": draft.source.platform,
            "requester": draft.source.requester,
            "parameters": [{"name": "version", "value": draft.source.version}],
        },
    }
    if draft.account is not None:
        payload["account"] = {
            "id": draft.account.id,
            "name": draft.account.name,
            "email": draft.account.email,
            "phone": draft.account.phone,
        }
    return payload


def _build_v1(draft: CartDraft) -> dict[str, object]:
    items: list[dict[str, object]] = []
    for item in draft.items:
        entry: dict[str, object] = {"id": item.id, "quantity": item.quantity}
        if item.garnish:
            entry["garnish"] = item.garnish
        items.append(entry)
    return {
        "merchant": {"id": draft.merchant_id},
        "address": draft.address,
        "items": items,
        "delivery": {
            "id": draft.delivery.id,
            "mode": draft.delivery.mode,
            # v1 **exige string**; boolean devolve CART-007 "Wrong input type".
            "now": "true" if draft.delivery.now else "false",
        },
    }


def validate(payload: dict[str, object], *, version: CartVersion = "v2") -> None:
    """Levanta o código que a API levantaria, na ordem medida de validação."""
    missing = [name for name in _REQUIRED_TOP_LEVEL if not _present(payload, name)]
    if missing:
        raise CartPayloadError(CART_MISSING, missing[0], f"faltando no payload: {missing}")

    merchant = payload.get("merchant")
    if not isinstance(merchant, dict) or not merchant.get("id"):
        raise CartPayloadError(CART_WRONG_TYPE, "merchant", "precisa objeto {id}, não id solto")

    address = payload.get("address")
    if not isinstance(address, dict):
        raise CartPayloadError(
            CART_WRONG_TYPE, "address", "precisa o objeto inteiro de GET /v1/customers/me/addresses"
        )

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise CartPayloadError(CART_MISSING, "items", "precisa lista não vazia")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CartPayloadError(CART_WRONG_TYPE, "items", f"item {index} não é objeto")
        quantity = item.get("quantity")
        if not isinstance(quantity, int) or quantity < 1:
            raise CartPayloadError(CART_WRONG_TYPE, "quantity", f"item {index}: inteiro >= 1")
        if version == "v1" and "subItems" in item:
            raise CartPayloadError(
                CART_WRONG_TYPE, "subItems", "na v1 complemento é `garnish`; `subItems` é da v2"
            )
        if version == "v2" and "garnish" in item:
            raise CartPayloadError(
                CART_WRONG_TYPE, "garnish", "na v2 complemento é `subItems`; `garnish` é da v1"
            )

    delivery = payload.get("delivery")
    if not isinstance(delivery, dict):
        raise CartPayloadError(CART_WRONG_TYPE, "delivery", "precisa objeto de entrega")
    now = delivery.get("now")
    if version == "v1":
        if not isinstance(now, str) or now not in {"true", "false"}:
            raise CartPayloadError(
                CART_WRONG_TYPE, "now", f'v1 exige a string "true"/"false", recebi {now!r}'
            )
    elif not isinstance(now, bool):
        raise CartPayloadError(
            CART_WRONG_TYPE, "now", f"v2 exige boolean, recebi {type(now).__name__}"
        )


def _present(payload: dict[str, object], name: str) -> bool:
    if name not in payload:
        return False
    value = payload[name]
    if value is None:
        return False
    return not (isinstance(value, (dict, list, str)) and len(value) == 0)


# resposta do cart
@dataclass(frozen=True, slots=True)
class Evaluator:
    """Avaliador de preço/disponibilidade do carrinho, com vencimento próprio."""

    id: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class CartSnapshot:
    """O ``201`` do v2: carrinho assinado + visão renderizada + assinatura.

    ``cart_response`` é **opaco** por contrato: vai inteiro para o checkout. O que
    este objeto expõe é só o que o fluxo precisa decidir: id, status, validade e os
    avaliadores.
    """

    cart_id: str
    status: str
    expires_at: str
    created_at: str
    signature: str
    evaluators: tuple[Evaluator, ...]
    cart_response: dict[str, object]


def snapshot_total(cart_response: dict[str, object]) -> float:
    """Total do snapshot **assinado**, em reais.

    Regra aprendida no pedido real: o total muda com o carrinho (troca de entrega de
    ``DEFAULT`` grátis para ``PRIORITY`` R$ 6,00 levou 31,89 → 37,89) e o ``amount``
    do checkout acompanha o **último** snapshot. Quem monta payload tem que ler
    daqui, nunca do valor que o humano aprovou minutos antes.
    """
    summary = cart_response.get("summary")
    if not isinstance(summary, dict):
        raise CartPayloadError(CART_MISSING, "summary", "carrinho sem resumo de preço")
    total = summary.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        raise CartPayloadError(CART_WRONG_TYPE, "total", f"total não numérico: {total!r}")
    return float(total)


def parse_cart_response(payload: dict[str, object]) -> CartSnapshot:
    """Lê o ``201`` de ``POST /site-api/v2/carts`` sem interpretar o conteúdo assinado."""
    cart = payload.get("cartResponse")
    if not isinstance(cart, dict):
        raise CartPayloadError(CART_MISSING, "cartResponse", "resposta sem carrinho assinado")
    signature = payload.get("signature")
    evaluators_raw = cart.get("evaluators")
    evaluators: list[Evaluator] = []
    if isinstance(evaluators_raw, list):
        for entry in evaluators_raw:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                evaluators.append(
                    Evaluator(id=entry["id"], expires_at=str(entry.get("expiresAt", "")))
                )
    return CartSnapshot(
        cart_id=str(cart.get("id", "")),
        status=str(cart.get("status", "")),
        expires_at=str(cart.get("expiresAt", "")),
        created_at=str(cart.get("createdAt", "")),
        signature=signature if isinstance(signature, str) else "",
        evaluators=tuple(evaluators),
        cart_response=cart,
    )
