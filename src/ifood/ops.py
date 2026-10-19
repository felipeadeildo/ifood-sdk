"""Operations shared by the MCP tools and the HTTP routes.

Both surfaces expose the same work, so the work lives here once and each surface only
decides how to present it. Every operation reads the session at call time.
"""

from typing import Any

from . import runtime


def session_status() -> dict[str, Any]:
    client = runtime.get_client()
    return {
        "logged_in": client.logged_in,
        "expires_in_seconds": client.session.expires_in(),
        "edge_cookies": client.session.edge_status(),
    }


def search_addresses(query: str) -> list[dict[str, Any]]:
    return runtime.get_client().locations.search(query)


def save_address(address: dict[str, Any]) -> dict[str, Any]:
    return runtime.get_client().customers.add_address(address).model_dump(by_alias=True)


def list_addresses() -> list[dict[str, Any]]:
    client = runtime.get_client()
    return [address.model_dump(by_alias=True) for address in client.customers.addresses()]


def list_orders(size: int = 5) -> list[dict[str, Any]]:
    client = runtime.get_client()
    return [order.model_dump(by_alias=True) for order in client.orders.recent(size)]


def get_order(order_id: str) -> dict[str, Any]:
    return runtime.get_client().orders.get(order_id).model_dump(by_alias=True)


def track_order(order_id: str) -> dict[str, Any]:
    client = runtime.get_client()
    order = client.orders.get(order_id)
    arrival = order.delivery.estimated_time_of_arrival if order.delivery else None
    return {
        "order_id": order.id,
        "number": order.number,
        "status": order.status,
        "delivery_code": order.delivery_code,
        "delivers_at": arrival.delivers_at if arrival else None,
        "delivers_end_at": arrival.delivers_end_at if arrival else None,
        "events": list(client.orders.events(order_id)),
    }


def merchant_items(merchant_id: str, *, latitude: float, longitude: float) -> list[dict[str, Any]]:
    return runtime.get_client().merchants.items(merchant_id, latitude=latitude, longitude=longitude)


def merchant_lookup(merchant_id: str) -> dict[str, Any]:
    return runtime.get_client().merchants.get(merchant_id).model_dump(by_alias=True)


def repeat_order(order_id: str | None = None) -> dict[str, Any]:
    return runtime.get_client().repeat(order_id).model_dump(by_alias=True)


def get_cart(cart_id: str) -> dict[str, Any]:
    """Read a cart, including its signature and the price the server would charge."""
    cart = runtime.get_client().carts.get(cart_id)
    return cart.model_dump(by_alias=True)


def create_cart_from_order(order_id: str) -> dict[str, Any]:
    """Build a cart from a past order and send it.

    Returns the cart id, the total and the signature. Nothing is charged here.
    """
    client = runtime.get_client()
    prepared = client.repeat(order_id)
    cart = client.carts.create(prepared.payload)
    snapshot = cart.cart
    return {
        "cart_id": snapshot.id if snapshot else None,
        "total": snapshot.total if snapshot else None,
        "signature": cart.signature,
        "diverged": prepared.diverged,
        "warnings": prepared.warnings,
    }


def set_payment_method(cart_id: str, method_id: str) -> dict[str, Any]:
    """Pick a payment method for the cart. The id comes from the cart snapshot."""
    cart = runtime.get_client().carts.set_payment_method(cart_id, [{"id": method_id}])
    return cart.model_dump(by_alias=True)


def place_order(cart_id: str, cpf_cnpj: str) -> dict[str, Any]:
    """Place the order. This creates a real order and returns the Pix code.

    The order stays CREATED until the Pix is paid, so this call charges nothing by itself.
    """
    client = runtime.get_client()
    placed = client.carts.place_order(cart_id, cpf_cnpj=cpf_cnpj)
    detail = client.orders.get(placed.order_id)
    return {
        "order_id": placed.order_id,
        "pix_qr_code": placed.pix_qr_code,
        "status": detail.status,
        "number": detail.number,
    }
