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


class FakeCartSnapshot:
    id = "cart-1"
    total = 28.89


class FakeCartResponse:
    cart = FakeCartSnapshot()
    signature = "sig"

    def model_dump(self, by_alias: bool = True) -> dict[str, object]:
        return {"cartResponse": {"id": "cart-1", "summary": {"total": 28.89}}, "signature": "sig"}


class FakePlaced:
    order_id = "order-1"
    pix_qr_code = "00020126"


class FakeCarts:
    def get(self, cart_id: str) -> FakeCartResponse:
        return FakeCartResponse()

    def create(self, payload: object) -> FakeCartResponse:
        return FakeCartResponse()

    def set_payment_method(self, cart_id: str, payload: object) -> FakeCartResponse:
        return FakeCartResponse()

    def place_order(self, cart_id: str, *, cpf_cnpj: str) -> FakePlaced:
        return FakePlaced()


class FakeClient:
    logged_in = True
    session = FakeSession()
    orders = FakeOrders()
    customers = FakeCustomers()
    carts = FakeCarts()

    def repeat(self, order_id: str | None = None) -> FakePrepared:
        return FakePrepared()
