import pytest

from ifood import Carts, Session, Transport


def test_checkout_rejects_object_cart_request() -> None:
    carts = Carts(Transport(Session()))
    with pytest.raises(ValueError, match="JSON string"):
        carts.checkout("cart-1", {"cartRequest": {"cartResponse": {}}})


def test_checkout_requires_cart_request() -> None:
    carts = Carts(Transport(Session()))
    with pytest.raises(ValueError, match="required"):
        carts.checkout("cart-1", {})


def test_voucher_route_is_the_v2_base() -> None:
    from ifood.wire import endpoints

    assert endpoints.CART_VOUCHER.startswith("/v2/carts/")
    assert endpoints.CART_VOUCHER_LEGACY.startswith("/v1/carts/")
    assert endpoints.bff_path("/v1/customers/me").endswith("/site-api/v1/customers/me")
