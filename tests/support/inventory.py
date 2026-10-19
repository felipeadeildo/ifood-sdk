"""Transforma uma captura ``requests.jsonl`` em inventário de endpoints.

Motivo: o objetivo do projeto é cobrir o fluxo inteiro (login → compra) e expor
isso como ferramenta. Nenhuma pessoa vai ler 25 MB de jsonl para descobrir que
``/v2/search/merchants`` leva ``latitude``, ``longitude``, ``channel`` e
``term``. Esta ferramenta lê a captura e cospe duas coisas:

- ``report/ENDPOINTS.md``: o mapa, com quem chamou o quê e com que status;
- ``tests/cassettes/``: um cassete por endpoint, pronto para a suíte de contrato.

A captura do ``record.mjs`` grava ``request`` e ``response`` como eventos soltos,
sem id de correlação. O pareamento aqui é FIFO por (método, url) e o que não
pareia é reportado como órfão, nunca escondido.
"""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .pending.http import (
    SENSITIVE_KEYS,
    Json,
    is_opaque_value,
    is_pii_path,
    looks_like_email,
    redact_params,
    redact_url,
)

#: Segmentos que são identidade, não rota: uuid, hash longo, número.
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HEXISH = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)
#: Segmento longo tipo token de GTM/assinatura (``JAtdqSvnXgtFS5-pSOgQa12…``).
_TOKENISH = re.compile(r"^[A-Za-z0-9_-]{20,}$")
_INT = re.compile(r"^\d+$")

STATIC_SUFFIXES = (
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".ico",
    ".mp4",
    ".html",
)


@dataclass(slots=True)
class Exchange:
    """Um par requisição/resposta já pareado."""

    method: str
    url: str
    status: int | None
    request_headers: dict[str, str] = field(default_factory=dict)
    response_headers: dict[str, str] = field(default_factory=dict)
    request_body: str | None = None
    response_body: str | None = None
    at: str | None = None


@dataclass(slots=True)
class Endpoint:
    """Agregado de todas as ocorrências de uma rota normalizada."""

    method: str
    host: str
    path: str
    query_keys: set[str] = field(default_factory=set)
    request_header_keys: set[str] = field(default_factory=set)
    statuses: Counter[int | None] = field(default_factory=Counter)
    content_types: Counter[str] = field(default_factory=Counter)
    initiators: Counter[str] = field(default_factory=Counter)
    count: int = 0

    @property
    def url(self) -> str:
        """URL só com o host e o path normalizado (query fora, por definição)."""
        return f"https://{self.host}{self.path}"

    @property
    def key(self) -> str:
        return f"{self.method} {self.host}{self.path}"


def normalize_path(path: str) -> str:
    """Troca identidade por marcador, para agrupar a mesma rota."""
    parts: list[str] = []
    for part in path.split("/"):
        if _UUID.match(part):
            parts.append("{uuid}")
        elif _HEXISH.match(part) and not part.isdigit():
            parts.append("{hash}")
        elif _TOKENISH.match(part):
            parts.append("{token}")
        elif _INT.match(part):
            parts.append("{n}")
        else:
            parts.append(part)
    return "/".join(parts)


def _split(url: str) -> tuple[str, str, str]:
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    return parsed.netloc, parsed.path or "/", parsed.query


#: Hosts que não são a API do iFood: telemetria de terceiros e borda de desafio.
#: Ficam fora do contrato por padrão (ver ``--include-third-party``).
_THIRD_PARTY_SUFFIXES = (
    "google.com",
    "google.com.br",
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "facebook.com",
    "facebook.net",
    "cloudflare.com",
    "braintreegateway.com",
    "paypal.com",
    "newrelic.com",
    "sentry.io",
)


def is_third_party(url: str) -> bool:
    """Verdadeiro para host que não é ``*.ifood.com.br``."""
    host = _split(url)[0]
    return not (host == "ifood.com.br" or host.endswith(".ifood.com.br"))


def is_static(url: str) -> bool:
    """Estático, telemetria de borda e esquema que não é HTTP (``blob:``, ``data:``)."""
    from urllib.parse import urlsplit

    if urlsplit(url).scheme not in {"http", "https"}:
        return True
    _, path, _ = _split(url)
    lowered = path.lower()
    if lowered.endswith(STATIC_SUFFIXES):
        return True
    return "/cdn-cgi/challenge-platform/" in lowered or "challenges.cloudflare.com" in url


def load_events(path: Path) -> Iterator[dict[str, Json]]:
    """Lê o jsonl e materializa ``bodyPath`` (corpo externo) em ``body``.

    O ``record.mjs`` novo grava corpo acima de 32 KB em ``bodies/<id>.txt`` e
    aponta com ``bodyPath`` relativo. Sem isso, todo payload grande (menu, feed,
    cassete de checkout) viraria "sem corpo".
    """
    base = path.parent
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        external = event.get("bodyPath")
        if isinstance(external, str) and not event.get("body"):
            body_file = base / external
            try:
                event["body"] = body_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                event["body"] = None
        yield event


def pair_exchanges(events: Iterable[dict[str, Json]]) -> tuple[list[Exchange], int]:
    """Pareia request/response por FIFO em (método, url). Devolve os pares e os órfãos."""
    pending: dict[tuple[str, str], list[Exchange]] = defaultdict(list)
    pairs: list[Exchange] = []
    orphans = 0
    for event in events:
        kind = event.get("type")
        url = event.get("url")
        if not isinstance(url, str):
            continue
        if kind == "request":
            method = str(event.get("method") or "GET")
            headers = event.get("headers")
            pending[(method, url)].append(
                Exchange(
                    method=method,
                    url=url,
                    status=None,
                    request_headers=dict(headers) if isinstance(headers, dict) else {},
                    request_body=event.get("postData")
                    if isinstance(event.get("postData"), str)
                    else None,
                    at=event.get("at") if isinstance(event.get("at"), str) else None,
                )
            )
        elif kind == "response":
            method = str(event.get("method") or "GET")
            queue = pending.get((method, url))
            if not queue:
                orphans += 1
                continue
            exchange = queue.pop(0)
            exchange.status = event.get("status") if isinstance(event.get("status"), int) else None
            headers = event.get("headers")
            exchange.response_headers = dict(headers) if isinstance(headers, dict) else {}
            body = event.get("body")
            exchange.response_body = body if isinstance(body, str) else None
            pairs.append(exchange)
    orphans += sum(len(queue) for queue in pending.values())
    pairs.extend(exchange for queue in pending.values() for exchange in queue)
    return pairs, orphans


def summarize(exchanges: Iterable[Exchange], *, include_static: bool = False) -> list[Endpoint]:
    endpoints: dict[str, Endpoint] = {}
    for exchange in exchanges:
        if not include_static and is_static(exchange.url):
            continue
        host, path, query = _split(exchange.url)
        normalized = normalize_path(path)
        key = f"{exchange.method} {host}{normalized}"
        endpoint = endpoints.get(key)
        if endpoint is None:
            endpoint = Endpoint(method=exchange.method, host=host, path=normalized)
            endpoints[key] = endpoint
        endpoint.count += 1
        for pair in query.split("&"):
            if pair:
                endpoint.query_keys.add(pair.split("=", 1)[0])
        endpoint.request_header_keys.update(exchange.request_headers)
        endpoint.statuses[exchange.status] += 1
        endpoint.content_types[exchange.response_headers.get("content-type", "?")] += 1
        referer = exchange.request_headers.get("referer") or exchange.request_headers.get("Referer")
        if referer:
            endpoint.initiators[referer] += 1
    return sorted(endpoints.values(), key=lambda item: (-item.count, item.key))


def _json_shape(payload: Json, depth: int = 0) -> Json:
    if depth > 3:
        return "<...>"
    if isinstance(payload, dict):
        return {key: _json_shape(value, depth + 1) for key, value in sorted(payload.items())[:40]}
    if isinstance(payload, list):
        return [_json_shape(payload[0], depth + 1)] if payload else ["<vazio>"]
    if isinstance(payload, bool):
        return "<bool>"
    if isinstance(payload, int | float):
        return "<number>"
    if payload is None:
        return "<null>"
    return "<string>"


def _shape_redacted(payload: Json, parent: str = "") -> Json:
    """Esqueleto com segredo e PII marcados: cassete nunca carrega token nem nome."""
    if isinstance(payload, dict):
        return {key: _redact_entry(key, value, parent) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_shape_redacted(item, parent) for item in payload[:1]]
    return _json_shape(payload)


_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LONG_SECRET = re.compile(r"\b[A-Za-z0-9+/=_-]{40,}\b")


def _scrub_text(raw: str | None) -> str | None:
    """Texto livre (HTML de borda, erro) sem JWT, e-mail ou blob longo."""
    if raw is None:
        return None
    cleaned = _JWT.sub("<jwt>", raw)
    cleaned = _EMAIL.sub("<email>", cleaned)
    cleaned = _LONG_SECRET.sub("<blob>", cleaned)
    return cleaned[:20_000]


def _redact_entry(key: str, value: Json, parent: str) -> Json:
    """Decide, por campo, entre redigir, mostrar forma ou descer."""
    if key.lower() in SENSITIVE_KEYS or is_pii_path(parent, key):
        return "<redacted>"
    if isinstance(value, str):
        if looks_like_email(value) or is_opaque_value(value):
            return "<redacted>"
        if value[:1] in {"{", "["} and len(value) > 200:
            return _nested_shape(value, key)
        return _json_shape(value)
    return _shape_redacted(value, key)


def _nested_shape(raw: str, parent: str) -> Json:
    """JSON aninhado em string (``cartRequest``): mostra a forma, nunca o conteúdo."""
    try:
        parsed = json.loads(raw)
    except ValueError:
        return "<json-aninhado-ilegivel>"
    if not isinstance(parsed, (dict, list)):
        return "<json-aninhado-escalar>"
    return _shape_redacted(parsed, parent)


def body_shape(raw: str | None) -> Json:
    if not raw:
        return None
    try:
        return _shape_redacted(json.loads(raw))
    except ValueError:
        return f"<texto {len(raw)}B>"


MANUAL = """## Credenciais e headers de sessão

Não há header de autenticação nem token nas rotas abaixo; elas passam com as
chaves estáticas do web app. Qualquer endpoint que apareça aqui com
`authorization` merece uma seção própria no ledger, não esta tabela.
"""


def representative(exchanges: Iterable[Exchange], endpoint: Endpoint) -> Exchange | None:
    """Primeira troca com resposta de sucesso que casa com o endpoint."""
    fallback: Exchange | None = None
    for exchange in exchanges:
        host, path, _ = _split(exchange.url)
        if exchange.method != endpoint.method or host != endpoint.host:
            continue
        if normalize_path(path) != endpoint.path:
            continue
        if exchange.status is not None and exchange.status < 400:
            return exchange
        fallback = fallback or exchange
    return fallback


#: Headers de requisição que valem como contrato. ``referer`` entra, mas passa por
#: ``redact_url`` porque já vimos telefone na query dele (``/entrar/celular?phone=``).
_REQUEST_HEADER_ALLOWLIST = frozenset(
    {"app_name", "platform", "app_version", "country", "accept", "user-agent", "referer"}
)


def _safe_header(key: str, value: str) -> str:
    return redact_url(value) if key.lower() == "referer" else value


def to_cassette(exchange: Exchange, *, name: str) -> dict[str, Json]:
    """Cassete no esquema da suíte de contrato (``ifood_contract.http.CASSETTE_SCHEMA``)."""
    content_type = exchange.response_headers.get("content-type", "")
    payload = body_shape(exchange.response_body)
    is_json = "json" in content_type
    return {
        "schema": 1,
        "recorded_at": exchange.at or "",
        "source": f"inventory:{name}",
        "request": {
            "method": exchange.method,
            "url": redact_url(exchange.url),
            "body": redact_params(
                exchange.request_body,
                exchange.request_headers.get("content-type")
                or exchange.request_headers.get("Content-Type", ""),
            ),
            "headers": {
                key: _safe_header(key, value)
                for key, value in exchange.request_headers.items()
                if key.lower() in _REQUEST_HEADER_ALLOWLIST
            },
        },
        "response": {
            "status": exchange.status if exchange.status is not None else 0,
            "headers": {
                key: value
                for key, value in exchange.response_headers.items()
                if key.lower() in {"content-type", "x-ifood-error-code", "server"}
            },
            "json": payload if is_json else None,
            "text": None if is_json else _scrub_text(exchange.response_body),
        },
    }


def slug(endpoint: Endpoint) -> str:
    raw = f"{endpoint.method}_{endpoint.host}{endpoint.path}"
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
