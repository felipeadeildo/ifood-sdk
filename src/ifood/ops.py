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
