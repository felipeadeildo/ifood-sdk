"""A small FastAPI service over the SDK, with the MCP server mounted at `/mcp`.

Reads work with the saved session. The write-shaped routes build a cart payload and
stop, for the same reason the MCP tools stop: the platform refuses writes from anything
but the browser that created the session.
"""

import hmac
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .. import ops
from ..errors import IfoodError
from ..mcp import asgi as mcp_asgi

TOKEN_ENV = "IFOOD_API_TOKEN"
MCP_TOKEN_ENV = "IFOOD_MCP_TOKEN"


def _expected_token() -> str:
    return os.environ.get(TOKEN_ENV, "")


async def require_token(request: Request) -> None:
    """Reject anything without the configured bearer token.

    A static token is the starting point. For a public deployment, validate an OAuth 2.1
    access token with a library instead of comparing a string.
    """
    expected = _expected_token()
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="token not configured")
    header = request.headers.get("authorization", "")
    if not hmac.compare_digest(header, f"Bearer {expected}"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def build_app() -> FastAPI:
    mcp_token = os.environ.get(MCP_TOKEN_ENV, _expected_token())
    mcp_app = mcp_asgi.build_app(token=mcp_token, streamable_http_path="/")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        # Starlette mounts get no lifespan of their own; run the MCP session
        # manager's startup and shutdown alongside the REST app's.
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(
        title="ifood-sdk", version="0.1.0", docs_url=None, redoc_url=None, lifespan=lifespan
    )
    guarded = [Depends(require_token)]
    app.mount("/mcp", mcp_app)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "ifood-sdk"}

    @app.get("/session", dependencies=guarded)
    def session_status() -> dict[str, Any]:
        return ops.session_status()

    @app.get("/orders", dependencies=guarded)
    def list_orders(size: int = 5) -> list[dict[str, Any]]:
        return ops.list_orders(size)

    @app.get("/orders/{order_id}", dependencies=guarded)
    def get_order(order_id: str) -> dict[str, Any]:
        return ops.get_order(order_id)

    @app.get("/orders/{order_id}/track", dependencies=guarded)
    def track_order(order_id: str) -> dict[str, Any]:
        return ops.track_order(order_id)

    @app.get("/addresses/search", dependencies=guarded)
    def search_addresses(query: str) -> list[dict[str, Any]]:
        return ops.search_addresses(query)

    @app.post("/addresses", dependencies=guarded)
    def save_address(address: dict[str, Any]) -> dict[str, Any]:
        return ops.save_address(address)

    @app.get("/merchants/{merchant_id}/items", dependencies=guarded)
    def merchant_items(merchant_id: str, latitude: float, longitude: float) -> list[dict[str, Any]]:
        return ops.merchant_items(merchant_id, latitude=latitude, longitude=longitude)

    @app.get("/carts/{cart_id}", dependencies=guarded)
    def get_cart(cart_id: str) -> dict[str, Any]:
        return ops.get_cart(cart_id)

    @app.post("/orders/{order_id}/cart", dependencies=guarded)
    def create_cart_from_order(order_id: str) -> dict[str, Any]:
        return ops.create_cart_from_order(order_id)

    @app.put("/carts/{cart_id}/payment-method", dependencies=guarded)
    def set_payment_method(cart_id: str, method_id: str) -> dict[str, Any]:
        return ops.set_payment_method(cart_id, method_id)

    @app.post("/carts/{cart_id}/checkout", dependencies=guarded)
    def place_order(cart_id: str, cpf_cnpj: str) -> dict[str, Any]:
        return ops.place_order(cart_id, cpf_cnpj)

    @app.get("/addresses", dependencies=guarded)
    def list_addresses() -> list[dict[str, Any]]:
        return ops.list_addresses()

    @app.post("/orders/{order_id}/repeat", dependencies=guarded)
    def repeat_order(order_id: str) -> dict[str, Any]:
        return ops.repeat_order(order_id)

    @app.get("/vouchers", dependencies=guarded)
    def list_vouchers(
        latitude: float, longitude: float, distance_km: float = 10.0
    ) -> dict[str, Any]:
        return ops.list_vouchers(latitude=latitude, longitude=longitude, distance_km=distance_km)

    @app.put("/carts/{cart_id}/voucher", dependencies=guarded)
    def apply_voucher(
        cart_id: str,
        token: str,
        code: str | None = None,
        campaign_id: str | None = None,
    ) -> dict[str, Any]:
        return ops.apply_voucher(cart_id, token, code=code, campaign_id=campaign_id)

    @app.exception_handler(IfoodError)
    async def _ifood_error(_: Request, error: IfoodError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=status.HTTP_502_BAD_GATEWAY)

    return app
