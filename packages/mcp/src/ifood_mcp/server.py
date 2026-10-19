"""Tools exposed to an agent.

Every tool is a read or a payload builder. Nothing here places an order: the iFood web API
refuses writes from any client whose TLS did not mint the session, so the honest surface is
reading and preparing.
"""

from typing import Any

from mcp.server import MCPServer
from pydantic import BaseModel

from . import session

SERVER_NAME = "ifood"
INSTRUCTIONS = """Unofficial client for the iFood consumer API.

Reads work with the user's saved session. Writes do not: the platform refuses them from
anything but the browser that created the session. So this server reads order history,
tracks deliveries, and builds a cart payload that the user sends in the app.
"""


class SessionStatus(BaseModel):
    logged_in: bool
    expires_in_seconds: int | None
    edge_cookies: dict[str, bool]


def build_server() -> MCPServer[Any]:
    mcp: MCPServer[Any] = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS)

    @mcp.tool()
    def session_status() -> SessionStatus:
        """Whether the saved session is usable, and how long the token lasts."""
        client = session.get_client()
        return SessionStatus(
            logged_in=client.logged_in,
            expires_in_seconds=client.session.expires_in(),
            edge_cookies=client.session.edge_status(),
        )

    @mcp.tool()
    def list_addresses() -> list[dict[str, Any]]:
        """Saved delivery addresses, with coordinates."""
        client = session.get_client()
        return [address.model_dump(by_alias=True) for address in client.customers.addresses()]

    @mcp.tool()
    def list_orders(size: int = 5) -> list[dict[str, Any]]:
        """Recent orders, newest first."""
        client = session.get_client()
        return [order.model_dump(by_alias=True) for order in client.orders.recent(size)]

    @mcp.tool()
    def get_order(order_id: str) -> dict[str, Any]:
        """One order: status, merchant, items, fees and payment."""
        return session.get_client().orders.get(order_id).model_dump(by_alias=True)

    @mcp.tool()
    def track_order(order_id: str) -> dict[str, Any]:
        """Status, estimated arrival, event timeline and the delivery code."""
        client = session.get_client()
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

    @mcp.tool()
    def merchant_lookup(merchant_id: str) -> dict[str, Any]:
        """Merchant name, status and minimum order. Needs no session."""
        return session.get_client().merchants.get(merchant_id).model_dump(by_alias=True)

    @mcp.tool()
    def repeat_last_order(order_id: str | None = None) -> dict[str, Any]:
        """Build the cart for a past order. Returns the payload and what changed.

        The payload is complete and validated, but sending it needs the app, because the
        platform refuses writes from anything but the browser that created the session.
        """
        prepared = session.get_client().repeat(order_id)
        return prepared.model_dump(by_alias=True)

    return mcp
