"""Serve the same tools over HTTP, behind a bearer token.

Set `IFOOD_MCP_TOKEN` to require `Authorization: Bearer <token>`. Without it the app still
binds to loopback and refuses to start on a public host.
"""

import hmac
import os

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
        expected = f"Bearer {self._token}"
        if not hmac.compare_digest(header, expected):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)


async def health(_: Request) -> Response:
    return JSONResponse({"ok": True, "server": "ifood-mcp"})


def build_app() -> Starlette:
    mcp = build_server()
    token = os.environ.get(TOKEN_ENV)
    security = TransportSecuritySettings(allowed_hosts=["*"], allowed_origins=["*"])
    routes = [
        Route("/health", health),
        Mount("/", app=mcp.streamable_http_app(transport_security=security)),
    ]
    return Starlette(routes=routes, middleware=[Middleware(BearerAuth, token=token or "")])
