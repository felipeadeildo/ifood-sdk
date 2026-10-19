# Roadmap

## Available today

| Capability | Call |
|---|---|
| OTP login | `Client(phone=...).login().verify(code)` |
| Session reuse | `Client()` |
| Profile | `client.customers.profile()` |
| Addresses | `client.customers.addresses()`, `locations.search()`, `add_address()` |
| Merchant detail | `client.merchants.get(id)` |
| Menu items | `client.merchants.items(id, latitude=, longitude=)` |
| Order history | `client.orders.recent(5)` |
| Order detail and tracking | `client.orders.get(id)`, `client.orders.events(id)` |
| Delivery code | `order.delivery_code` |
| Reorder | `client.orders.reorder(order, latitude=, longitude=)` |
| Cart payload | `client.carts.build(...)` |
| Cart create and read | `client.carts.create()`, `client.carts.get()` |
| Cart item update | `client.carts.update_item()` |
| Payment method | `client.carts.set_payment_method()` |
| Checkout | `client.carts.place_order(cart_id, cpf_cnpj=...)` |
| MCP server | `python -m ifood.mcp`, fourteen tools |
| HTTP service | `uvicorn ifood.api:build_app --factory`, bearer token |

## Not covered

| Item | Why | What would close it |
|---|---|---|
| Voucher listing | the wallet route was never seen on the wire | one capture of the voucher screen |
| Voucher apply | `PUT /v2/carts/{id}/voucher` comes from the bundle, unverified | one call with a real coupon |
| Reverse geocode | route name assumed from the module, never called | one call with coordinates |
| E-mail OTP | only the WhatsApp shape was measured | test the e-mail channel |
| Grouped catalog | PerimeterX | a browser session per call |
| Search | PerimeterX | same |

## Next

| Item | Why it matters |
|---|---|
| Token refresh without OTP | the session lasts minutes, and a refresh token already arrives with the login |
| Tests in CI | only the docs workflow runs today |
| Publish to PyPI | install currently needs the git repository |
| `update_item` in MCP and API | the SDK has it, the two surfaces do not |
