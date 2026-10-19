from pathlib import Path

from ifood import FileStore, MemoryStore, Order, Session
from ifood.models import CartResponse


def test_file_store_round_trips_a_session(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "session.json"
    store = FileStore(path)
    assert store.load() is None

    store.save(Session(access_token="jwt", refresh_token="refresh", cookies={"aDeviceId": "d"}))

    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "jwt"
    assert loaded.cookies["aDeviceId"] == "d"
    assert path.stat().st_mode & 0o077 == 0


def test_memory_store_is_a_drop_in() -> None:
    store = MemoryStore()
    store.save(Session(access_token="jwt"))
    assert store.load() is not None


def test_order_exposes_typed_fields_and_keeps_extras() -> None:
    payload = {
        "id": "o-1",
        "orderNumber": "7782",
        "lastStatus": "CONFIRMED",
        "merchant": {"id": "m-1", "name": "Pizza Prime"},
        "verificationCodes": [{"name": "DELIVERY_CODE", "value": "1841"}],
        "somethingNew": {"kept": True},
    }
    order = Order.model_validate(payload)
    assert order.order_number == "7782"
    assert order.merchant is not None and order.merchant.name == "Pizza Prime"
    assert order.delivery_code == "1841"
    assert order.model_dump(by_alias=True)["somethingNew"] == {"kept": True}


def test_cart_response_reads_the_snapshot_and_total() -> None:
    payload = {
        "data": {"id": "cart-1", "summary": {"total": {"value": 37.89}}},
        "signature": "sig-96-chars",
    }
    cart = CartResponse.model_validate(payload)
    assert cart.cart is not None
    assert cart.cart.total == {"value": 37.89}
    assert cart.signature == "sig-96-chars"
