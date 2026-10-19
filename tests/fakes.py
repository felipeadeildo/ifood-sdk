"""Fakes shared by the API and MCP tests."""

from typing import Any


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
