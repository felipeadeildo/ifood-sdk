# MCP server

`ifood-mcp` exposes the client to an agent. Same rules as the SDK: reads work, writes do
not, and the server says so instead of failing in a confusing way.

```bash
uv run --project packages/mcp python -m ifood_mcp
```

That speaks MCP over stdio, which is what a local host launches. The tools:

| Tool | What it returns |
|---|---|
| `session_status` | whether the saved session works, token lifetime, edge cookies |
| `list_addresses` | saved addresses with coordinates |
| `list_orders` | recent orders, newest first |
| `get_order` | one order: status, merchant, items, fees, payment |
| `track_order` | status, arrival window, event timeline, delivery code |
| `merchant_lookup` | merchant name, status, minimum order |
| `repeat_last_order` | validated cart payload plus what changed |

The last one is the case the project exists for. It builds the payload; sending it happens
in the app, because the platform refuses writes from anything but the browser that created
the session.

## Over HTTP, with a token

```bash
IFOOD_MCP_TOKEN=secret uv run --project packages/mcp uvicorn ifood_mcp.asgi:build_app --factory
```

`GET /health` answers without a token. Everything under `/mcp` requires
`Authorization: Bearer <token>`. Without `IFOOD_MCP_TOKEN` the app still runs, so bind it to
loopback and never expose it.

For a public deployment the next step is OAuth 2.1: the MCP Python SDK expects a
`TokenVerifier`, and the token should be validated by a library, not by hand. The static
bearer here is a starting point, not the end state.

## Tests

Tools are tested in memory, with the same `Client` the SDK ships: no port, no subprocess.
`packages/mcp/tests/test_tools.py` replaces the client factory with a fake and asserts the
shape each tool returns.
