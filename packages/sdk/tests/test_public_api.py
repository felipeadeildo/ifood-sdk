"""The surface people type. If this reads badly, the library reads badly."""

from pathlib import Path

import pytest

import ifood
from ifood import Order, Phone, Session


def test_phone_accepts_what_people_actually_type() -> None:
    for raw in ("+55 11 90000-0000", "(11) 90000-0000", "11900000000", "5511900000000"):
        phone = Phone.parse(raw)
        assert (phone.country_code, phone.area_code, phone.number) == (55, "11", "900000000")


def test_phone_with_too_few_digits_is_refused() -> None:
    with pytest.raises(ValueError, match="not a phone"):
        Phone.parse("1841")


def test_a_client_without_session_is_not_logged_in(tmp_path: Path) -> None:
    client = ifood.Client(store=ifood.FileStore(tmp_path / "missing.json"))
    assert client.logged_in is False


def test_a_client_reuses_the_saved_session(tmp_path: Path) -> None:
    store = ifood.FileStore(tmp_path / "session.json")
    store.save(Session(access_token="jwt", refresh_token="refresh"))
    client = ifood.Client(store=store)
    assert client.logged_in is True
    assert client.session.access_token == "jwt"


def test_order_reads_as_a_sentence() -> None:
    order = Order.model_validate(
        {
            "id": "o-1",
            "orderNumber": "7782",
            "lastStatus": "CONFIRMED",
            "merchant": {"id": "m-1", "name": "Pizza Prime"},
        }
    )
    assert order.number == "7782"
    assert order.status == "CONFIRMED"
    assert order.merchant is not None
    assert order.merchant.name == "Pizza Prime"


def test_reorder_accepts_the_order_object() -> None:
    seen: list[str] = []

    class FakeTransport:
        def get(self, path: str, **_: object) -> dict[str, object]:
            seen.append(path)
            return {"id": "o-1"}

    orders = ifood.Orders(FakeTransport())  # type: ignore[arg-type]
    order = Order(id="o-1")
    orders.reorder(order, latitude=-23.6, longitude=-46.6)
    assert "/o-1/reorder" in seen[0]


def test_login_and_verify_chain_on_the_same_client(tmp_path: Path) -> None:
    store = ifood.FileStore(tmp_path / "session.json")
    client = ifood.Client(phone="+55 11 90000-0000", store=store)

    class FakeChallenge:
        timeout_seconds = 60

        def verify(self, code: str) -> None:
            assert code == "123456"
            client.session.access_token = "jwt"
            client.session.refresh_token = "refresh"

    client.auth.start_otp = lambda *a, **k: FakeChallenge()  # type: ignore[method-assign]
    assert client.login() is client
    assert client.verify("123456") is client
    assert client.logged_in is True
    assert store.load() is not None


def test_cart_items_take_options_positionally() -> None:
    from ifood import CartItem, SubItem

    item = CartItem("burger", 2, SubItem("cheese"), SubItem("bacon"), observation="sem cebola")
    assert item.quantity == 2
    assert [sub.id for sub in item.sub_items] == ["cheese", "bacon"]
    assert item.observation == "sem cebola"


def test_cart_build_takes_the_fields_directly() -> None:
    from ifood import Account, CartItem, SubItem

    client = ifood.Client()
    payload = client.carts.build(
        merchant_id="m-1",
        address={"id": "a-1"},
        items=[CartItem("i-1", 1, SubItem("o-1"))],
        account=Account("acc-1"),
        version="v2",
    )
    assert payload["merchant"] == {"id": "m-1"}
    assert payload["items"][0]["subItems"] == [{"id": "o-1", "quantity": 1}]


def test_cart_build_accepts_our_own_objects() -> None:
    from ifood import CartItem, Merchant, SubItem
    from ifood.models import Address, Coordinates

    client = ifood.Client()
    address = Address(
        id="a-1",
        streetName="Av. Paulista",
        streetNumber="1000",
        coordinates=Coordinates(latitude=-23.5, longitude=-46.6),
    )
    merchant = Merchant(id="m-1", name="Pizza Prime")
    account = ifood.Account("acc-1", "User", "user@example.com", 55, "11", "900000000")

    payload = client.carts.build(
        merchant=merchant,
        address=address,
        items=[CartItem("i-1", 1, SubItem("o-1"))],
        account=account,
    )
    assert payload["merchant"] == {"id": "m-1", "name": "Pizza Prime"}
    assert payload["address"]["streetName"] == "Av. Paulista"
    assert payload["address"]["coordinates"]["latitude"] == -23.5
    assert payload["account"]["phone"]["number"] == "900000000"


def test_cart_build_accepts_raw_dicts_too() -> None:
    from ifood import CartItem, SubItem

    client = ifood.Client()
    payload = client.carts.build(
        merchant={"id": "m-1"},
        address={"id": "a-1"},
        items=[{"id": "i-1", "quantity": 2, "subItems": [{"id": "o-1", "quantity": 1}]}],
        account={"id": "acc-1"},
    )
    assert payload["items"][0]["quantity"] == 2
    assert payload["items"][0]["subItems"] == [{"id": "o-1", "quantity": 1}]
    assert CartItem("i-1").sub_items == ()
    assert SubItem("o-1").quantity == 1


def test_session_account_falls_back_to_the_user_id() -> None:
    from ifood import Account

    client = ifood.Client(session=Session(access_token="jwt", user_id="acc-9"))
    account = client.cart_account()
    assert isinstance(account, Account)
    assert account.id == "acc-9"


def test_login_keeps_the_account_email_for_the_last_step() -> None:
    class FakeTransport:
        def __init__(self) -> None:
            self.bodies: list[dict[str, object]] = []

        def post(self, path: str, *, json_body: object) -> dict[str, object]:
            self.bodies.append({"path": path, "body": json_body})
            return {"key": "k-1", "timeout_in_seconds": 60}

    transport = FakeTransport()
    auth = ifood.Auth(transport)  # type: ignore[arg-type]
    challenge = auth.start_otp("+55 11 90000-0000", email="user@example.com")
    assert challenge.identifier["email"] == "user@example.com"
    assert challenge.identifier["phone"]["area_code"] == "11"
