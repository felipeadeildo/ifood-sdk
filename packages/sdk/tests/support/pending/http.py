"""HTTP com dois modos: replay de cassete (padrão, offline) e gravação (rede).

O modo replay é a razão de existir da suíte: rodar contrato em CI sem tocar na
borda do iFood, sem consumir rate limit e sem vazar IP de quem roda. O modo
gravação é o único que usa ``httpx`` de verdade, e fica atrás de ``--record``.
"""

import json
import re
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit, urlunsplit

import httpx

from .config import BASE_URLS, app_headers
from .errors import IfoodApiError

type Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]


class CassetteError(RuntimeError):
    """Cassete ausente, corrompido ou de esquema desconhecido."""


CASSETTE_SCHEMA = 1

#: O RE é de uso pessoal: nada de rajada. Uma chamada a cada ``MIN_INTERVAL`` segundos.
MIN_INTERVAL = 1.2

#: Headers que mudam a cada resposta, ou descrevem a codificação do transporte
#: (o cassete guarda o corpo já decodificado), e não são contrato.
_VOLATILE_HEADERS = frozenset(
    {
        "date",
        "set-cookie",
        "server-timing",
        "strict-transport-security",
        "alt-svc",
        "expires",
        "age",
        "cache-control",
        "content-length",
        "content-encoding",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "cf-cache-status",
        "cf-ray",
        "vary",
        "x-request-id",
        "x-kong-request-id",
        "x-kong-response-latency",
        "x-kong-upstream-latency",
        "x-kong-proxy-latency",
        "x-envoy-upstream-service-time",
        "x-ifood-geocode-session-id",
    }
)


def _canonical(method: str, url: str) -> str:
    """Chave de comparação: método + host + path + query com pares ordenados."""
    parsed = httpx.URL(url)
    pairs = sorted(f"{key}={value}" for key, value in parsed.params.multi_items())
    return f"{method.upper()} {parsed.scheme}://{parsed.host}{parsed.path}?{'&'.join(pairs)}"


#: A partir daqui o valor é opaco por definição: ``key`` do desafio OTP (45 chars b64),
#: uuid de conta, assinatura. Nome de campo não basta para decidir — ``key:"city"``
#: é uma regra de geocode legítima e aparece em cassete.
OPAQUE_VALUE_MIN_LEN = 28
_OPAQUE_VALUE = re.compile(r"^[A-Za-z0-9+/=_.:-]+$")


_EMAILISH = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")


def is_opaque_value(value: str) -> bool:
    """Valor sem espaço, longo e alfanumérico: token/id/assinatura, não conteúdo."""
    return len(value) >= OPAQUE_VALUE_MIN_LEN and bool(_OPAQUE_VALUE.match(value))


def looks_like_email(value: str) -> bool:
    """E-mail — inclusive quando aparece colado em dígitos.

    Medido no checkout: ``cybersourceFingerprint`` vinha como
    ``ALGUEM@EXEMPLO.COM211``. Nome de campo não avisa, então o valor decide.
    """
    return bool(_EMAILISH.match(value.strip())) or ("@" in value[:80] and "." in value[:80])


#: Caminhos (pai, filho) que são PII mesmo com nome de campo inocente. Ex.: o web
#: manda ``account: {name: ...}`` no corpo do carrinho — ``name`` sozinho é legítimo
#: (nome de restaurante/item), então a regra precisa do pai.
PII_PATHS = frozenset({("account", "name"), ("customer", "name"), ("account", "phone")})


def is_pii_path(parent: str, key: str) -> bool:
    return (parent.lower(), key.lower()) in PII_PATHS


def _redact_nested_json(url: str, raw: str, parent: str) -> Json:
    """Redige JSON que veio serializado dentro de uma string."""
    try:
        parsed = json.loads(raw)
    except ValueError:
        return "<json-aninhado-ilegivel>"
    if not isinstance(parsed, (dict, list)):
        return "<json-aninhado-escalar>"
    redacted = redact_json(url, parsed, parent=parent)
    return json.dumps(redacted, ensure_ascii=False)


def redact_json(url: str, payload: Json, *, parent: str = "") -> Json:
    """Troca o que identifica a máquina ou autoriza alguém.

    Cassete é arquivo de repositório: ``access_token``/``refresh_token``/
    ``authorization`` nunca podem sair daqui, mesmo que o alvo seja de uso pessoal.
    """
    if not isinstance(payload, dict):
        return payload
    if url.endswith("/ip") and isinstance(payload.get("ip"), str):
        return {**payload, "ip": "203.0.113.7"}
    redacted: dict[str, Json] = {}
    for key, value in payload.items():
        if (
            key.lower() in SENSITIVE_KEYS
            or is_pii_path(parent, key)
            or (isinstance(value, str) and is_opaque_value(value))
            or (isinstance(value, str) and looks_like_email(value))
        ):
            redacted[key] = "<redacted>"
        elif isinstance(value, str) and value[:1] in {"{", "["} and len(value) > 200:
            # JSON aninhado em string (medido: `cartRequest` do checkout, 25 KB).
            # Se ficar cru, o cassete guarda conta, endereço e assinatura juntos.
            redacted[key] = _redact_nested_json(url, value, key)
        elif isinstance(value, dict):
            redacted[key] = redact_json(url, value, parent=key)
        elif isinstance(value, list):
            redacted[key] = [
                redact_json(url, item, parent=key) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


#: Chaves cujo *valor* nunca entra em cassete. O nome da chave é contrato; o valor não.
SECRET_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "id_token",
        "token",
        "authorization",
        "password",
        "passwd",
        "senha",
        "cpf",
        "email",
        "username",
        "user",
        "login",
        # "code" fica de fora: código de erro (``IFCS-2001``) é contrato e precisa
        # aparecer no cassete. Código de OTP chega como ``auth_code``/``otp``.
        "otp",
        "mfa_code",
        "challenge_code",
        "code_verifier",
        "client_secret",
        "secret",
        "x-ifood-device-payment-secret",
        "cookie",
        "set-cookie",
        "auth_code",
    }
)

#: Dados pessoais que não podem ir para cassete versionado. Separados de
#: ``SECRET_KEYS`` porque a origem é outra: não são credencial, são PII.
PII_KEYS = frozenset(
    {
        "email",
        "contact_emails",
        "device_id",
        "cpfcnpj",
        "cpf_cnpj",
        "cybersourcefingerprint",
        "clearsalefingerprint",
        "qrcode",
        "pixqrcode",
        "verificationcodes",
        "shortid",
        "tax_payer_identification_number",
        "emailorphone",
        "challengeemail",
        "ip",
        "phone",
        "phones",
        "cpf",
        "account_id",
        "customer_id",
        "external_id",
        "externalid",
        "provider_id",
        "address",
        "addresses",
        "street",
        "streetname",
        "street_name",
        "streetnumber",
        "street_number",
        "neighborhood",
        "zipcode",
        "zip_code",
        "postalcode",
        "coordinates",
        "latitude",
        "longitude",
        "lat",
        "lng",
        "full_name",
        "first_name",
        "last_name",
        "display_id",
    }
)

#: Tudo que vira ``<redacted>`` no cassete.
SENSITIVE_KEYS = SECRET_KEYS | PII_KEYS

#: Únicos parâmetros de query cujo *valor* pode ser gravado. A regra é fail-closed:
#: o valor de qualquer outro parâmetro vira ``<redacted>``, porque o contrato é o
#: nome do parâmetro. Motivo: ``emailOrPhone=82900000000`` passou pelo filtro por
#: nome e vazou telefone para o cassete.
SAFE_QUERY_VALUES = frozenset(
    {
        "channel",
        "size",
        "page",
        "alias",
        "type",
        "preference",
        "locale",
        "country",
        "platform",
        "sort",
        "include_details",
    }
)


def redact_url(url: str) -> str:
    """Mantém host, path e nomes de query; troca valor sensível por ``<redacted>``."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept: list[str] = []
    for chunk in parts.query.split("&"):
        name, _, value = chunk.partition("=")
        safe = name.lower() in SAFE_QUERY_VALUES and len(value) < 24
        kept.append(chunk if safe else f"{name}=<redacted>")
    return urlunsplit(parts._replace(query="&".join(kept)))


def redact_params(raw: str | None, content_type: str) -> Json:
    """Forma do corpo enviado: nomes de parâmetro sempre, valores só se não forem segredo.

    É isso que responde "grant de senha? PKCE?": ``grant_type=password`` e
    ``code_challenge_method=S256`` ficam gravados; ``password`` vira ``<redacted>``.
    """
    if not raw:
        return None
    if "json" in content_type:
        try:
            parsed = json.loads(raw)
        except ValueError:
            return "<body não-JSON>"
        return redact_json("", parsed)
    try:
        pairs = httpx.QueryParams(raw).multi_items()
    except Exception:
        return "<body opaco>"
    return {
        key: ("<redacted>" if key.lower() in SENSITIVE_KEYS or is_opaque_value(value) else value)
        for key, value in pairs
    }


class CassetteTransport(httpx.BaseTransport):
    """Serve a resposta gravada; aborta com mensagem clara se a chamada divergir."""

    def __init__(self, path: Path, *, record: bool) -> None:
        self._path = path
        self._record = record
        self._live = httpx.HTTPTransport()
        self._recorded: dict[str, Json] = {}
        if not record:
            self._recorded = self._load()

    def _load(self) -> dict[str, Json]:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != CASSETTE_SCHEMA:
            raise CassetteError(f"cassete em formato desconhecido: {self._path}")
        return payload

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._record:
            return self._record_request(request)
        return self._replay(request)

    def _replay(self, request: httpx.Request) -> httpx.Response:
        body = request.read()
        sent = f"{request.method} {request.url}"
        expected_request = self._recorded.get("request")
        expected = expected_request.get("url") if isinstance(expected_request, dict) else None
        if isinstance(expected, str) and _canonical(request.method, str(request.url)) != _canonical(
            request.method, expected
        ):
            raise AssertionError(
                f"chamada fora do cassete {self._path.name}\n"
                f"  esperado: {expected}\n"
                f"  enviado : {sent}\n"
                f"  corpo   : {body[:200]!r}\n"
                "Regrave com: uv run pytest --record <teste>"
            )
        response = self._recorded.get("response")
        if not isinstance(response, dict):
            raise CassetteError(f"cassete sem resposta: {self._path}")
        headers = response.get("headers")
        status = response.get("status")
        if not isinstance(status, int):
            raise CassetteError(f"cassete sem status: {self._path}")
        content = response.get("json")
        if content is None:
            text = response.get("text")
            content_bytes = (text if isinstance(text, str) else "").encode()
        else:
            content_bytes = json.dumps(content).encode()
        return httpx.Response(
            status_code=status,
            headers=dict(headers) if isinstance(headers, dict) else {},
            content=content_bytes,
            request=request,
        )

    def _record_request(self, request: httpx.Request) -> httpx.Response:
        response = self._live.handle_request(request)
        response.read()
        self._write(request, response)
        return response

    def _write(self, request: httpx.Request, response: httpx.Response) -> None:
        content_type = response.headers.get("content-type", "")
        body_text = request.content.decode("utf-8", "replace")
        body: Json = response.text[:20_000]
        if "json" in content_type:
            try:
                body = redact_json(str(request.url), json.loads(response.text))
            except ValueError:
                pass
        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in _VOLATILE_HEADERS
        }
        payload: dict[str, Json] = {
            "schema": CASSETTE_SCHEMA,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "request": {
                "method": request.method,
                "url": str(request.url),
                # Guardamos só os headers que são contrato; os de sessão são gerados a cada execução.
                "headers": {
                    key: value
                    for key, value in request.headers.items()
                    if key.lower()
                    in {
                        "app_name",
                        "platform",
                        "app_version",
                        "country",
                        "accept",
                        "user-agent",
                        "content-type",
                    }
                },
                "authorization": "presente" if "authorization" in request.headers else None,
                "body": redact_params(body_text, request.headers.get("content-type", "")),
            },
            "response": {
                "status": response.status_code,
                "headers": headers,
                "json": body if "json" in content_type else None,
                "text": None if "json" in content_type else body,
            },
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def close(self) -> None:
        self._live.close()


class ContractClient:
    """Chamadas do contrato. Sem cassete, fala com a rede (só em ``--live``/``--record``)."""

    def __init__(
        self,
        *,
        cassette: Path | None = None,
        record: bool = False,
        session_id: str | None = None,
        device_id: str | None = None,
        authorization: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.device_id = device_id or str(uuid.uuid4())
        self._authorization = authorization
        self._extra_headers = dict(extra_headers or {})
        self._network = cassette is None or record
        self._last_call = 0.0
        transport: httpx.BaseTransport
        if cassette is not None:
            transport = CassetteTransport(cassette, record=record)
        else:
            transport = httpx.HTTPTransport()
        self._client = httpx.Client(transport=transport, timeout=20.0, follow_redirects=False)

    def _headers(self, *, application_key: bool, authorization: bool = True) -> dict[str, str]:
        headers = app_headers(self.session_id, self.device_id)
        if not application_key:
            headers.pop("x-application-key")
            headers.pop("x-client-application-key")
        if authorization and self._authorization:
            headers["authorization"] = self._authorization
        headers.update(self._extra_headers)
        return headers

    def get(
        self,
        host: str,
        path: str,
        *,
        application_key: bool = True,
        authorization: bool = True,
        **params: str | float,
    ) -> httpx.Response:
        url = BASE_URLS[host].rstrip("/") + path
        self._throttle()
        return self._client.get(
            url,
            params=params,
            headers=self._headers(application_key=application_key, authorization=authorization),
        )

    def post_form(
        self,
        host: str,
        path: str,
        *,
        form: Mapping[str, str],
        authorization: bool = True,
        **params: str | float,
    ) -> httpx.Response:
        """``application/x-www-form-urlencoded``, que é o que OAuth2 exige no token."""
        url = BASE_URLS[host].rstrip("/") + path
        self._throttle()
        return self._client.post(
            url,
            data=dict(form),
            params=params,
            headers=self._headers(application_key=True, authorization=authorization),
        )

    def post_json(
        self,
        host: str,
        path: str,
        *,
        payload: Json,
        authorization: bool = True,
        **params: str | float,
    ) -> httpx.Response:
        url = BASE_URLS[host].rstrip("/") + path
        self._throttle()
        return self._client.post(
            url,
            json=payload,
            params=params,
            headers=self._headers(application_key=True, authorization=authorization),
        )

    def _throttle(self) -> None:
        """Mantém o ritmo da diretriz de escopo: no máximo ~1 req/s, sempre."""
        if not self._network:
            return
        wait = MIN_INTERVAL - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def get_json(
        self,
        host: str,
        path: str,
        *,
        application_key: bool = True,
        **params: str | float,
    ) -> Json:
        response = self.get(host, path, application_key=application_key, **params)
        error = IfoodApiError.from_response(response.status_code, str(response.url), response.text)
        if error is not None:
            raise error
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def dig(payload: Json, pointer: str) -> Json:
    """Percorre ``a.b.c`` em JSON, tolerando listas (índice inteiro)."""
    node: Json = payload
    for part in pointer.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict):
            node = node[part]
        else:
            raise KeyError(f"{pointer} não existe: {part!r} não é objeto nem lista")
    return node
