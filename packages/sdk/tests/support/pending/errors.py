"""Erro de domínio do iFood: status, código de aplicação e envelope.

Um teste que só olha o status não distingue as recusas que existem hoje no fluxo.
São **três famílias de envelope**, e o cliente precisa das três:

1. **plano** — ``{"code": "IFCS-2001", "message": "Merchant not found", "details": [...]}``
   Usado por marketplace/logistics/consumer (IFCS-*, IFSL-*, IFSD-*). O código
   também vai no header ``x-ifood-error-code``.
2. **aninhado** — ``{"error": {"code": "CART-006", "message": "..."}}``
   Usado pelo serviço de carrinho (CART-*, ITEM-*). Ler só ``body["code"]`` aqui
   devolve ``None`` e transforma erro de negócio em "erro desconhecido".
3. **borda** — HTML do Cloudflare/Akamai, ou Kong ``{"message": "Not Found"}``.
   Não é a API falando: é PX/CF/Akamai barrando, ou rota que não existe.

O envelope do serviço de checkout (``SCO-3000`` em ``/orders/{id}/reorder``) ainda
não foi capturado com corpo: o parser aceita plano ou aninhado, e o teste
``test_envelope_of_reorder_is_not_assumed`` lembra que é desconhecido.
"""

import json

#: Chaves onde os serviços já foram vistos colocando o código, no envelope plano.
_CODE_KEYS = ("code", "errorCode", "error_code")
_MESSAGE_KEYS = ("message", "localizedMessage", "userMessage", "error_description", "detail")
_DETAIL_KEYS = ("details", "errors")

#: Envelopes conhecidos, na ordem em que são testados.
ENVELOPE_FLAT = "flat"
ENVELOPE_NESTED = "nested"
ENVELOPE_KONG = "kong"
ENVELOPE_EDGE = "edge"
ENVELOPE_UNKNOWN = "unknown"


def _first_str(payload: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _details(payload: dict[str, object]) -> tuple[str, ...]:
    for key in _DETAIL_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return tuple(item for item in value if isinstance(item, str))
        if isinstance(value, str) and value:
            return (value,)
    return ()


class IfoodApiError(RuntimeError):
    """Resposta >= 400 de um host do iFood."""

    def __init__(
        self,
        *,
        status: int,
        url: str,
        code: str | None,
        message: str | None,
        body: str,
        details: tuple[str, ...] = (),
        envelope: str = ENVELOPE_UNKNOWN,
        header_code: str | None = None,
    ) -> None:
        self.status = status
        self.url = url
        self.code = code or header_code
        self.message = message
        self.body = body
        self.details = details
        self.envelope = envelope
        self.header_code = header_code
        super().__init__(f"{status} {self.code or '-'} {url}: {(message or body)[:200]}")

    @property
    def is_edge(self) -> bool:
        """Barreira de borda (Cloudflare/Akamai) ou rota ausente no Kong.

        Nada aqui é contrato da API: significa "o pedido não chegou no serviço".
        """
        return self.envelope in {ENVELOPE_EDGE, ENVELOPE_KONG}

    @property
    def is_auth_missing(self) -> bool:
        """Gateway recusou por falta de JWT: ``401 {"message":"no jwt token"}``.

        Caso medido no BFF: o cookie ``aAccessToken`` existe, mas o header
        ``Authorization: Bearer`` não foi enviado. Corpo plano, sem ``code`` — o
        cliente que só olha ``code`` não descobre que é falta de header.
        """
        return self.status == 401 and "jwt" in (self.message or "").lower()

    @property
    def is_rate_limited(self) -> bool:
        return self.status == 429

    @property
    def is_business_rule(self) -> bool:
        """Código de aplicação presente: a API respondeu, a regra recusou."""
        return bool(self.code) and not self.is_edge

    @property
    def retryable(self) -> bool:
        """Só o que pode mudar sozinho. Regra de negócio nunca é retry."""
        return self.is_rate_limited or self.status >= 500

    @classmethod
    def from_response(
        cls,
        status: int,
        url: str,
        body: str,
        *,
        response_headers: dict[str, str] | None = None,
    ) -> IfoodApiError | None:
        """Devolve ``None`` quando o status é de sucesso."""
        if status < 400:
            return None
        headers = {key.lower(): value for key, value in (response_headers or {}).items()}
        header_code = headers.get("x-ifood-error-code")

        parsed: object = None
        try:
            parsed = json.loads(body)
        except ValueError, TypeError:
            parsed = None

        code: str | None = None
        message: str | None = None
        details: tuple[str, ...] = ()
        envelope = ENVELOPE_UNKNOWN

        if isinstance(parsed, dict):
            nested = parsed.get("error")
            if isinstance(nested, dict):
                envelope = ENVELOPE_NESTED
                code = _first_str(nested, _CODE_KEYS)
                message = _first_str(nested, _MESSAGE_KEYS)
                details = _details(nested)
            else:
                code = _first_str(parsed, _CODE_KEYS)
                message = _first_str(parsed, _MESSAGE_KEYS)
                details = _details(parsed)
                # Kong responde sem ``code``: só ``{"message":"Not Found"}``.
                if not code and (message or "").strip() == "Not Found":
                    envelope = ENVELOPE_KONG
                elif code or message:
                    envelope = ENVELOPE_FLAT
        elif (
            "<html" in body[:200].lower()
            or headers.get("cf-mitigated")
            or headers.get("server", "").lower() == "akamaighost"
            or "Access Denied" in body[:200]
        ):
            envelope = ENVELOPE_EDGE

        return cls(
            status=status,
            url=url,
            code=code,
            message=message,
            body=body,
            details=details,
            envelope=envelope,
            header_code=header_code,
        )
