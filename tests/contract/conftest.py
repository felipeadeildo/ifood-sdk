"""Fixtures da suíte de contrato.

Três modos, escolhidos por flag:

- padrão: replay dos cassetes em ``tests/cassettes/``, zero rede;
- ``--record``: bate na rede e regrava o cassete do teste que rodar;
- ``--live``: bate na rede e **não** grava (para checar deriva de contrato).

Os testes marcados ``live`` só rodam com uma das duas flags de rede, porque
eles existem justamente para comparar a rede com o cassete.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from support.pending.http import ContractClient, Json, dig

if TYPE_CHECKING:
    from collections.abc import Iterator

CASSETTES = Path(__file__).resolve().parents[1] / "cassettes"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("ifood")
    group.addoption("--live", action="store_true", help="bate na rede (sem gravar cassete)")
    group.addoption(
        "--record", action="store_true", help="bate na rede e regrava o cassete do teste"
    )
    group.addoption(
        "--jar",
        action="store",
        default=None,
        metavar="PATH",
        help="jar Netscape da sessão do operador (fumaça por endpoint); env: IFOOD_JAR",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    live = bool(config.getoption("--live"))
    record = bool(config.getoption("--record"))

    def only_live(reason: str) -> pytest.MarkDecorator:
        return pytest.mark.skip(reason=reason)

    skip_offline = only_live("precisa de --live ou --record: bate na rede")
    skip_record = only_live("teste de deriva não grava cassete: rode com --live")
    skip_session = pytest.mark.skip(
        reason="fumaça de sessão: precisa de --live e --jar (cookies do operador)"
    )
    for item in items:
        if "session" in item.keywords and not live:
            item.add_marker(skip_session)
            continue
        if "live" not in item.keywords:
            continue
        if record:
            item.add_marker(skip_record)
        elif not live:
            item.add_marker(skip_offline)


@pytest.fixture
def client(request: pytest.FixtureRequest) -> Iterator[ContractClient]:
    """Cliente preso ao cassete homônimo do teste."""
    config = request.config
    record = bool(config.getoption("--record"))
    live = bool(config.getoption("--live"))
    if live and record:
        pytest.fail("--live e --record são exclusivos")
    cassette = None if live else CASSETTES / f"{request.node.name}.json"
    with ContractClient(cassette=cassette, record=record) as instance:
        yield instance


@pytest.fixture(scope="session")
def cassette_dir() -> Path:
    return CASSETTES


class ClientFactory:
    """Cria ``ContractClient`` preso a um cassete, ou solto na rede em ``--record``."""

    cassettes = CASSETTES

    def make(
        self,
        *,
        cassette: Path | None = None,
        record: bool = False,
        authorization: str | None = None,
    ) -> ContractClient:
        return ContractClient(cassette=cassette, record=record, authorization=authorization)


@pytest.fixture
def client_factory() -> ClientFactory:
    return ClientFactory()


@pytest.fixture
def capture_client(request: pytest.FixtureRequest, client_factory: ClientFactory) -> ClientFactory:
    """Cliente para rotas que exigem login: pula enquanto não houver cassete.

    Ordem de resolução: ``--record`` (grava, exige token no ambiente) → cassete
    existente (replay) → skip explicando o comando que falta.
    """
    import os

    cassette = client_factory.cassettes / f"{request.node.name}.json"
    if request.config.getoption("--record"):
        token = os.environ.get("IFOOD_AUTHORIZATION") or None
        if token is None and "with_authorization" in request.node.name:
            pytest.skip("defina IFOOD_AUTHORIZATION para gravar o caso autenticado")
        return client_factory.make(cassette=cassette, record=True, authorization=token)
    if not cassette.exists():
        pytest.skip(
            "aguardando captura de login: rode "
            f"`uv run pytest --record {request.node.name}` "
            f"(cassete esperado: {cassette.name})"
        )
    return client_factory.make(cassette=cassette)


def json_shape(payload: Json) -> Json:
    """Esqueleto comparável: tipos no lugar de valores, chaves ordenadas.

    Serve para detectar deriva de contrato sem falhar por um preço que mudou.
    """
    if isinstance(payload, dict):
        return {key: json_shape(value) for key, value in sorted(payload.items())}
    if isinstance(payload, list):
        return [json_shape(payload[0])] if payload else ["<vazio>"]
    if isinstance(payload, bool):
        return "<bool>"
    if isinstance(payload, int | float):
        return "<number>"
    if payload is None:
        return "<null>"
    return "<string>"


__all__ = ["CASSETTES", "dig", "json_shape"]


@pytest.fixture(scope="session")
def jar_path(request: pytest.FixtureRequest) -> Path:
    """Jar da sessão: ``--jar`` ou ``IFOOD_JAR``. Sem jar, o teste de sessão pula."""
    import os

    configured = request.config.getoption("--jar") or os.environ.get("IFOOD_JAR")
    if not configured:
        pytest.skip("sem jar de sessão: passe --jar <cookies.txt> ou IFOOD_JAR")
    path = Path(configured).expanduser()
    if not path.exists():
        pytest.skip(f"jar configurado não existe: {path}")
    return path


@pytest.fixture(scope="session")
def session(jar_path: Path):
    """Cliente HTTP com o jar do operador, mais o relatório de validade."""
    from support.pending.session import Session, build_client, read_jar

    cookies = read_jar(jar_path)
    session = Session(client=build_client(cookies), cookies=cookies, path=jar_path)
    yield session
    session.close()
