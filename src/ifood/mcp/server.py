"""Tools exposed to an agent.

Every tool is a read or a payload builder. Nothing here places an order: the iFood web API
refuses writes from any client whose TLS did not mint the session, so the honest surface is
reading and preparing.
"""

from typing import Any

from mcp.server import MCPServer
from pydantic import BaseModel

from .. import ops

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
        return SessionStatus(**ops.session_status())

    @mcp.tool()
    def list_addresses() -> list[dict[str, Any]]:
        """Saved delivery addresses, with coordinates."""
        return ops.list_addresses()

    @mcp.tool()
    def search_addresses(query: str) -> list[dict[str, Any]]:
        """Turn a typed address into candidate places with coordinates."""
        return ops.search_addresses(query)

    @mcp.tool()
    def save_address(address: dict[str, Any]) -> dict[str, Any]:
        """Save a new delivery address. Needs the fields the web client sends."""
        return ops.save_address(address)

    @mcp.tool()
    def list_orders(size: int = 5) -> list[dict[str, Any]]:
        """Recent orders, newest first."""
        return ops.list_orders(size)

    @mcp.tool()
    def get_order(order_id: str) -> dict[str, Any]:
        """One order: status, merchant, items, fees and payment."""
        return ops.get_order(order_id)

    @mcp.tool()
    def track_order(order_id: str) -> dict[str, Any]:
        """Status, estimated arrival, event timeline and the delivery code."""
        return ops.track_order(order_id)

    @mcp.tool()
    def merchant_items(merchant_id: str, latitude: float, longitude: float) -> list[dict[str, Any]]:
        """Menu items with prices and choice groups for one merchant."""
        return ops.merchant_items(merchant_id, latitude=latitude, longitude=longitude)

    @mcp.tool()
    def merchant_lookup(merchant_id: str) -> dict[str, Any]:
        """Merchant name, status and minimum order. Needs no session."""
        return ops.merchant_lookup(merchant_id)

    @mcp.tool()
    def repeat_last_order(order_id: str | None = None) -> dict[str, Any]:
        """Build the cart for a past order. Returns the payload and what changed.

        The payload is complete and validated, but sending it needs the app, because the
        platform refuses writes from anything but the browser that created the session.
        """
        return ops.repeat_order(order_id)

    return mcp
