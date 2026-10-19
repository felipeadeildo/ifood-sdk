# Roadmap

## Available today

| Capability | Call | Notes |
|---|---|---|
| OTP login | `Client(phone=...).login().verify(code)` | code arrives on WhatsApp, valid 60 s |
| Session reuse | `Client()` | reads `~/.config/ifood-sdk/session.json` |
| Profile | `client.customers.profile()` | |
| Addresses | `client.customers.addresses()`, `locations.search()`, `add_address()` | done |
| Merchant | `client.merchants.get(id)` | no auth needed |
| Order history | `client.orders.recent(5)` | |
| Order detail | `client.orders.get(id)` | status, fees, payments |
| Tracking events | `client.orders.events(id)` | timeline with timestamps |
| Delivery code | `order.delivery_code` | four digits for the courier |
| Reorder | `client.orders.reorder(order, latitude=…, longitude=…)` | previous bag |
| Cart payload | `client.carts.build(merchant_id=…, …)` | validated, no network |
| MCP server | `uv run python -m ifood.mcp` | seven tools, stdio or HTTP |
| HTTP service | `uvicorn ifood.api:build_app --factory` | seven routes, bearer token |

## Blocked

| Item | Reason | What would unblock it |
|---|---|---|
| Cart write | Cloudflare challenges POST from non-browser TLS | browser-originated session |
| Checkout | same | same |
| Menu | PerimeterX | browser-originated session |
| Search | PerimeterX | browser-originated session |
| Voucher listing | no measured route | a capture of the voucher wallet |

## Next

| Item | Why | Effort |
|---|---|---|
| `ifood-api` | let other machines use the flows | small |
| `ifood-mcp` | seven tools, token-protected HTTP; needs OAuth for public use | done |
| `ifood-api` | seven routes, token-protected; needs OAuth and per-user sessions | done |
| E-mail OTP | second login path | needs measurement |
| Social login | third login path | needs measurement |
| Token refresh | sessions last 2 h | small, needs a live test |
| 429 backoff | gateway rate limits | small |
| Constant drift check | `app_version` rotates per deploy | small |
