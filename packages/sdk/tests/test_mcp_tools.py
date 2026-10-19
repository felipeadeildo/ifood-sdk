"""Tools tested in memory: no port, no subprocess, no network."""

import asyncio
from typing import Any

import pytest
from mcp import Client

from ifood import runtime
from ifood.mcp.server import build_server

from .fakes import FakeClient


@pytest.fixture(autouse=True)
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "get_client", lambda: FakeClient())


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def call(name: str, arguments: dict[str, Any] | None = None) -> Any:
    async def go() -> Any:
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return run(go())


def test_tools_are_listed() -> None:
    async def names() -> list[str]:
        async with Client(build_server()) as client:
            tools = await client.list_tools()
            return [tool.name for tool in tools.tools]

    assert run(names()) == [
        "session_status",
        "list_addresses",
        "list_orders",
        "get_order",
        "track_order",
        "merchant_lookup",
        "repeat_last_order",
    ]


def test_session_status_reports_the_token() -> None:
    payload = call("session_status").structured_content or {}
    assert payload["logged_in"] is True
    assert payload["expires_in_seconds"] == 7000
    assert payload["edge_cookies"]["cf_clearance"] is True


def test_list_orders_returns_the_payload() -> None:
    payload = call("list_orders", {"size": 1}).structured_content or {}
    assert payload["result"][0]["orderNumber"] == "7782"


def test_track_order_bundles_status_and_events() -> None:
    payload = call("track_order", {"order_id": "order-1"}).structured_content or {}
    assert payload["status"] == "CONFIRMED"
    assert payload["delivery_code"] == "1841"
    assert [event["value"] for event in payload["events"]] == ["CREATED", "PLACED"]


def test_repeat_last_order_returns_a_payload() -> None:
    payload = call("repeat_last_order").structured_content or {}
    assert payload["merchant"] == "Pizza Prime"
    assert payload["warnings"] == []
