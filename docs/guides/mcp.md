# MCP server

`ifood-sdk[mcp]` exposes the client to an agent over the Model Context Protocol.

```bash
uv run python -m ifood.mcp
```

That speaks MCP over stdio, which is how a local host launches it. The tools:

| Tool | What it returns |
|---|---|
| `session_status` | whether the saved session works, token lifetime, edge cookies |
| `list_addresses` | saved addresses with coordinates |
| `search_addresses` | place search with coordinates |
| `save_address` | save a new address |
| `list_orders` | recent orders, newest first |
| `get_order` | one order: status, merchant, items, fees, payment |
| `track_order` | status, arrival window, event timeline, delivery code |
| `merchant_lookup` | merchant name, status, minimum order |
| `repeat_last_order` | validated cart payload plus what changed |

`repeat_last_order` is the case the project exists for. It builds the payload; sending it
happens in the app, because the platform refuses writes from anything but the browser that
created the session.

## Over HTTP, with a token

```bash
IFOOD_MCP_TOKEN=secret uv run uvicorn ifood.mcp.asgi:build_app --factory
```

`GET /health` answers without a token, and everything under `/mcp` requires
`Authorization: Bearer <token>`. Without `IFOOD_MCP_TOKEN` the app still runs, so bind it to
loopback and never expose it.

For a public deployment the next step is OAuth 2.1: the MCP Python SDK expects a
`TokenVerifier`, and the token should be validated by a library, not by hand.

## How it is built

The server uses the official SDK (`mcp.server.MCPServer`, v2, Streamable HTTP). Each tool
is a thin wrapper over `ifood.ops`, the same module the HTTP service calls.

Tools are tested in memory with the SDK's own `Client`, so a test needs no port and no
subprocess: `tests/test_mcp_tools.py`.
