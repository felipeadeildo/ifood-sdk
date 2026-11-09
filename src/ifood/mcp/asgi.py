"""Serve the same tools over HTTP, behind a bearer token.

Set `IFOOD_MCP_TOKEN` to require `Authorization: Bearer <token>`. Without it the app still
binds to loopback and refuses to start on a public host. `build_app(token=...)` takes the
token directly, which is how the REST service mounts this app under `/mcp`.

Follows the SDK recipe from docs/run/asgi.md: a mounted sub-app's lifespan never runs,
so this app enters `session_manager.run()` itself. DNS rebinding protection stays off
because the allowlist has no wildcard and the bearer token is the access control.
"""

import hmac
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .server import build_server

TOKEN_ENV = "IFOOD_MCP_TOKEN"


class BearerAuth:
    """Reject anything without the configured bearer token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self._app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        header = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
        if not hmac.compare_digest(header, f"Bearer {self._token}"):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)


def build_app(token: str | None = None, *, streamable_http_path: str = "/mcp") -> Starlette:
    mcp = build_server()
    token = token if token is not None else os.environ.get(TOKEN_ENV)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> Response:
        return JSONResponse({"ok": True, "server": "ifood-mcp"})

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncGenerator[None]:
        async with mcp.session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/health", health),
            Mount(
                "/",
                app=mcp.streamable_http_app(
                    streamable_http_path=streamable_http_path,
                    transport_security=TransportSecuritySettings(
                        enable_dns_rebinding_protection=False
                    ),
                ),
            ),
        ],
        lifespan=lifespan,
        middleware=[Middleware(BearerAuth, token=token or "")],
    )
