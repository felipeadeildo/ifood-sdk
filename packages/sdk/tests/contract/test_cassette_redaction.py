"""Guarda do repositório: cassete versionado não pode carregar segredo nem PII.

Motivo: os cassetes vêm de capturas reais, e as capturas trazem JWT, telefone,
e-mail e endereço do operador. Um cassete vazado é pior que teste faltando — ele
fica no histórico. Aqui a regra é executável, não um aviso no README.

Se este teste falhar: conserte a redação (``ifood_contract/http.py`` e
``inventory.py``) e regrave. Nunca edite o cassete à mão para "passar".
"""

import json
import re
from pathlib import Path

import pytest
from support.pending.http import SECRET_KEYS, SENSITIVE_KEYS

CASSETTES = Path(__file__).resolve().parents[1] / "cassettes"

#: Padrões que não podem aparecer em texto nenhum do arquivo. Note que telefone
#: **não** entra aqui: sequência de 10 dígitos aparece em bundle de terceiro
#: (``1003696969`` de GTM) e o guarda viraria ruído. Telefone é checado por campo
#: (nome de chave + formato), logo abaixo.
_PATTERNS = {
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}

#: Blob longo é checado **por valor**, não no texto cru: chave de Server Action do
#: Next.js é hash hex de 64 chars e é legítima (o valor dela é que não pode vazar).
_BLOB = re.compile(r"^[A-Za-z0-9+/=_-]{40,}$")

#: Campo que, por nome, guardaria telefone; e o formato de telefone em si.
_PHONE_KEY = re.compile(r"phone|telefone|celular|emailorphone", re.IGNORECASE)
_PHONE_VALUE = re.compile(r"^\+?\d{10,13}$")

#: Na raiz da pasta o cassete é gravado pela suíte com dado público; aí só
#: credencial é proibida (endereço de rua pode ficar).
_SECRET_ONLY = frozenset(SECRET_KEYS) | {"access_token", "refresh_token", "authorization"}

#: Valores-sentinela que podem aparecer no lugar do dado real.
_PLACEHOLDERS = {"<redacted>", "<string>", "<number>", "<bool>", "<null>", "<lista>", "203.0.113.7"}


def _files() -> list[Path]:
    if not CASSETTES.exists():
        return []
    return sorted(CASSETTES.rglob("*.json"))


def _walk(payload: object, path: str = "") -> list[tuple[str, str]]:
    """Devolve (chave, valor) de todo escalar string, com caminho legível."""
    found: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.extend(_walk(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_walk(value, f"{path}[{index}]"))
    elif isinstance(payload, str):
        found.append((path.rsplit(".", 1)[-1].split("[")[0], payload))
    return found


def _is_inventory(cassette: Path) -> bool:
    """Cassete de inventário vem de sessão real do operador: PII obrigatoriamente fora.

    Os cassetes da raiz são gravados pela própria suíte contra dado público
    ("Avenida Paulista, 1000"), e ali o valor real é o que os testes afirmam
    (coordenada, número, CEP). Nesses, só segredo é proibido.
    """
    return cassette.parent.name == "inventory"


@pytest.mark.parametrize("cassette", _files(), ids=lambda path: path.name)
def test_cassette_has_no_secret_or_pii(cassette: Path) -> None:
    raw = cassette.read_text(encoding="utf-8")
    for name, pattern in _PATTERNS.items():
        match = pattern.search(raw)
        assert match is None, f"{cassette.name}: {name} no cassete -> {match.group(0)[:40]!r}"

    payload = json.loads(raw)
    strict = _is_inventory(cassette)
    for key, value in _walk(payload):
        if key == "ip":
            continue
        if _PHONE_KEY.search(key) and _PHONE_VALUE.match(value):
            raise AssertionError(f"{cassette.name}: telefone cru em `{key}`")
        if _BLOB.match(value):
            raise AssertionError(f"{cassette.name}: valor opaco não redigido em `{key}`")
        forbidden = key.lower() in SENSITIVE_KEYS if strict else key.lower() in _SECRET_ONLY
        if forbidden:
            assert value in _PLACEHOLDERS, (
                f"{cassette.name}: campo sensível `{key}` com valor real no cassete"
            )


def test_redaction_patterns_actually_match_known_shapes() -> None:
    """O guarda precisa ser capaz de falhar; senão é decoração."""
    assert _PATTERNS["jwt"].search("eyJraWQiOiJiNjRjNjZmZS00ZWY5LT.abcdefghijkl")
    assert _PATTERNS["email"].search("alguem@example.com")
    assert _PHONE_VALUE.match("82900000000")
    assert not _PATTERNS["email"].search("<redacted>")


def test_cassette_count_matches_inventory_when_present() -> None:
    """Se o inventário foi gerado, ele existe de verdade (não é pasta vazia)."""
    inventory = CASSETTES / "inventory"
    if not inventory.exists():
        pytest.skip("inventário não gerado nesta máquina")
    assert len(list(inventory.glob("*.json"))) >= 10
