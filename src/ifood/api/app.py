"""A small FastAPI service over the SDK.

Reads work with the saved session. The one write-shaped route builds a cart payload and
stops, for the same reason the MCP tools stop: the platform refuses writes from anything
but the browser that created the session.
"""

import hmac
import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .. import ops
from ..errors import IfoodError

TOKEN_ENV = "IFOOD_API_TOKEN"


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
    app = FastAPI(title="ifood-sdk", version="0.1.0", docs_url=None, redoc_url=None)
    guarded = [Depends(require_token)]

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

    @app.get("/addresses", dependencies=guarded)
    def list_addresses() -> list[dict[str, Any]]:
        return ops.list_addresses()

    @app.post("/orders/{order_id}/repeat", dependencies=guarded)
    def repeat_order(order_id: str) -> dict[str, Any]:
        return ops.repeat_order(order_id)

    @app.exception_handler(IfoodError)
    async def _ifood_error(_: Request, error: IfoodError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=status.HTTP_502_BAD_GATEWAY)

    return app
