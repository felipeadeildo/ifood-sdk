"""The HTTP service, tested through the app object. No server, no network."""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ifood import runtime
from ifood.api import build_app

from .fakes import FakeClient


@pytest.fixture(autouse=True)
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "get_client", lambda: FakeClient())


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IFOOD_API_TOKEN", "secret")
    with TestClient(build_app()) as test_client:
        yield test_client


def test_health_needs_no_token(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_everything_else_needs_the_token(client: TestClient) -> None:
    assert client.get("/orders").status_code == 401
    ok = client.get("/orders", headers={"authorization": "Bearer secret"})
    assert ok.status_code == 200
    assert ok.json()[0]["orderNumber"] == "7782"


def test_track_returns_status_and_events(client: TestClient) -> None:
    response = client.get("/orders/order-1/track", headers={"authorization": "Bearer secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CONFIRMED"
    assert body["delivery_code"] == "1841"


def test_repeat_returns_a_payload_not_an_order(client: TestClient) -> None:
    response = client.post("/orders/order-1/repeat", headers={"authorization": "Bearer secret"})
    assert response.status_code == 200
    assert response.json()["merchant"] == "Pizza Prime"


def test_without_a_configured_token_the_service_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IFOOD_API_TOKEN", raising=False)
    response = TestClient(build_app()).get("/orders")
    assert response.status_code == 503


def test_mcp_is_mounted_and_guarded(client: TestClient) -> None:
    """The streamable HTTP MCP lives at /mcp, behind the same bearer token."""
    assert client.get("/mcp/health").status_code == 401
    ok = client.get("/mcp/health", headers={"authorization": "Bearer secret"})
    assert ok.status_code == 200
    assert ok.json()["server"] == "ifood-mcp"


def test_mcp_tools_answer_over_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client(url) has no auth hook, so wrap the transport with the bearer header."""
    monkeypatch.setenv("IFOOD_API_TOKEN", "secret")
    import httpx
    from mcp import Client
    from mcp.client._transport import Transport
    from mcp.client.streamable_http import streamable_http_client

    class AuthedTransport(Transport):
        def __init__(self, app: Any, headers: dict[str, str]) -> None:
            self._http = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            )
            self._http.headers.update(headers)
            self._cm: Any = None

        async def __aenter__(self) -> Any:
            self._cm = streamable_http_client("http://testserver/mcp", http_client=self._http)
            return await self._cm.__aenter__()

        async def __aexit__(self, *exc: object) -> None:
            await self._cm.__aexit__(*exc)
            await self._http.aclose()

    async def go() -> Any:
        app = build_app()
        # The MCP session manager only exists inside its lifespan, so open it here,
        # in the same loop the MCP client runs on.
        async with (
            app.router.lifespan_context(app),
            Client(AuthedTransport(app, {"authorization": "Bearer secret"})) as stream,
        ):
            return await stream.call_tool("list_orders", {"size": 1})

    result = asyncio.run(go())
    assert result.content
