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
| `list_vouchers` | voucher wallet: code, conditions, and the token to apply one |
| `apply_voucher` | apply a coupon to a cart, returns the discounted cart |
| `repeat_last_order` | validated cart payload plus what changed |

`repeat_last_order` is the case the project exists for. It builds the payload; sending it
happens in the app, because the catalog and search routes refuse anything but the browser that
created the session.

## Over HTTP, with a token

```bash
IFOOD_MCP_TOKEN=secret uv run uvicorn ifood.mcp.asgi:build_app --factory
```

This speaks Streamable HTTP. Clients connect to `http://host:8000/mcp`. The same MCP server
also rides inside the REST service: `uvicorn ifood.api:build_app --factory` mounts it at
`/mcp`, where the token defaults to `IFOOD_API_TOKEN` when `IFOOD_MCP_TOKEN` is unset.

The MCP endpoint requires `Authorization: Bearer <token>`. Without a token the app still
runs, so bind it to loopback and never expose it.

For a public deployment the next step is OAuth 2.1: the MCP Python SDK expects a
`TokenVerifier`, and the token should be validated by a library, not by hand.

## How it is built

The server uses the official SDK (`mcp.server.MCPServer`, v2, Streamable HTTP). Each tool
is a thin wrapper over `ifood.ops`, the same module the HTTP service calls.

Tools are tested in memory with the SDK's own `Client`, so a test needs no port and no
subprocess: `tests/test_mcp_tools.py`.
| `get_cart` | items, total, signature and lease |
| `create_cart_from_order` | build a cart from a past order and send it |
| `set_payment_method` | pick a payment method for the cart |
| `place_order` | place the order and return the Pix code |
| `merchant_items` | menu items with prices and choices |
