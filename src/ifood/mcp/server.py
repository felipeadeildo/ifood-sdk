"""Tools exposed to an agent.

Reads use the saved session. Writes work only while the session is fresh: the platform
refuses them from any client whose TLS did not mint the session, which is why the tools
that send a cart need the browser-minted jar.
"""

from typing import Any

from mcp.server import MCPServer
from pydantic import BaseModel

from .. import ops

SERVER_NAME = "ifood"
INSTRUCTIONS = """Unofficial client for the iFood consumer API.

Reads work with the user's saved session. Cart writes and checkout work only while that
session is fresh; the platform refuses them from anything but the browser that created
it. Voucher coupons are applied to a cart with a token from list_vouchers, and the token
rotates on every listing call.
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
    def get_cart(cart_id: str) -> dict[str, Any]:
        """Read a cart: items, total, signature and the lease on the quote."""
        return ops.get_cart(cart_id)

    @mcp.tool()
    def create_cart_from_order(order_id: str) -> dict[str, Any]:
        """Build a cart from a past order and send it. Returns cart id, total and signature."""
        return ops.create_cart_from_order(order_id)

    @mcp.tool()
    def set_payment_method(cart_id: str, method_id: str) -> dict[str, Any]:
        """Pick a payment method for the cart. The id comes from the cart snapshot."""
        return ops.set_payment_method(cart_id, method_id)

    @mcp.tool()
    def place_order(cart_id: str, cpf_cnpj: str) -> dict[str, Any]:
        """Place the order and return the Pix code. Nothing is charged until it is paid."""
        return ops.place_order(cart_id, cpf_cnpj)

    @mcp.tool()
    def merchant_items(merchant_id: str, latitude: float, longitude: float) -> list[dict[str, Any]]:
        """Menu items with prices and choice groups for one merchant."""
        return ops.merchant_items(merchant_id, latitude=latitude, longitude=longitude)

    @mcp.tool()
    def merchant_lookup(merchant_id: str) -> dict[str, Any]:
        """Merchant name, status and minimum order. Needs no session."""
        return ops.merchant_lookup(merchant_id)

    @mcp.tool()
    def list_vouchers(
        latitude: float, longitude: float, distance_km: float = 10.0
    ) -> dict[str, Any]:
        """Voucher wallet: code, status and conditions, plus the token to apply one."""
        return ops.list_vouchers(latitude=latitude, longitude=longitude, distance_km=distance_km)

    @mcp.tool()
    def apply_voucher(
        cart_id: str,
        token: str,
        code: str | None = None,
        campaign_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply a voucher to the cart; `token` comes from list_vouchers."""
        return ops.apply_voucher(cart_id, token, code=code, campaign_id=campaign_id)

    @mcp.tool()
    def repeat_last_order(order_id: str | None = None) -> dict[str, Any]:
        """Build the cart for a past order. Returns the payload and what changed.

        The payload is complete and validated, but sending it needs the app, because the
        platform refuses writes from anything but the browser that created the session.
        """
        return ops.repeat_order(order_id)

    return mcp
