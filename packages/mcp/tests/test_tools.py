"""Tools tested in memory: no port, no subprocess, no network."""

import asyncio
from typing import Any

import pytest
from mcp import Client

from ifood_mcp import session
from ifood_mcp.server import build_server


class FakeSession:
    def expires_in(self) -> int:
        return 7000

    def edge_status(self) -> dict[str, bool]:
        return {"cf_clearance": True, "_px3": False}


class FakeOrder:
    id = "order-1"
    number = "7782"
    status = "CONFIRMED"
    delivery_code = "1841"
    delivery = None

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {"id": self.id, "orderNumber": self.number, "lastStatus": self.status}


class FakeOrders:
    def recent(self, size: int = 5) -> list[FakeOrder]:
        return [FakeOrder()][:size]

    def get(self, order_id: str) -> FakeOrder:
        assert order_id == "order-1"
        return FakeOrder()

    def events(self, order_id: str) -> list[dict[str, Any]]:
        return [{"value": "CREATED"}, {"value": "PLACED"}]


class FakeCustomers:
    def addresses(self) -> list[object]:
        class Address:
            def model_dump(self, **_: Any) -> dict[str, Any]:
                return {"id": "addr-1", "streetName": "Av. Paulista"}

        return [Address()]


class FakePrepared:
    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {"merchant": "Pizza Prime", "warnings": [], "payload": {"items": []}}


class FakeClient:
    logged_in = True
    session = FakeSession()
    orders = FakeOrders()
    customers = FakeCustomers()

    def repeat(self, order_id: str | None = None) -> FakePrepared:
        return FakePrepared()


@pytest.fixture(autouse=True)
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session, "get_client", lambda: FakeClient())


def call(name: str, arguments: dict[str, Any] | None = None) -> Any:
    async def run() -> Any:
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return asyncio.run(run())


def test_tools_are_listed() -> None:
    async def run() -> list[str]:
        async with Client(build_server()) as client:
            tools = await client.list_tools()
            return [tool.name for tool in tools.tools]

    names = asyncio.run(run())
    assert names == [
        "session_status",
        "list_addresses",
        "list_orders",
        "get_order",
        "track_order",
        "merchant_lookup",
        "repeat_last_order",
    ]


def test_session_status_reports_the_token() -> None:
    result = call("session_status")
    payload = result.structured_content or {}
    assert payload["logged_in"] is True
    assert payload["expires_in_seconds"] == 7000
    assert payload["edge_cookies"]["cf_clearance"] is True


def test_list_orders_returns_typed_payload() -> None:
    result = call("list_orders", {"size": 1})
    payload = result.structured_content or {}
    orders = payload.get("result", payload)
    assert orders and orders[0]["orderNumber"] == "7782"


def test_track_order_bundles_status_and_events() -> None:
    result = call("track_order", {"order_id": "order-1"})
    payload = result.structured_content or {}
    assert payload["status"] == "CONFIRMED"
    assert payload["delivery_code"] == "1841"
    assert [event["value"] for event in payload["events"]] == ["CREATED", "PLACED"]


def test_repeat_last_order_returns_a_payload() -> None:
    result = call("repeat_last_order")
    payload = result.structured_content or {}
    assert payload["merchant"] == "Pizza Prime"
    assert payload["warnings"] == []
