<div align="center">

<img src="docs/assets/logo.svg" alt="ifood-sdk" width="72" />

# ifood-sdk

Unofficial Python client for the iFood consumer API.

[![tests](https://github.com/felipeadeildo/ifood-sdk/actions/workflows/tests.yml/badge.svg)](https://github.com/felipeadeildo/ifood-sdk/actions/workflows/tests.yml)
[![docs](https://img.shields.io/badge/docs-felipeadeildo.github.io%2Fifood--sdk-0e3b2e)](https://felipeadeildo.github.io/ifood-sdk/)
[![python](https://img.shields.io/badge/python-3.14+-3cc488)](https://github.com/felipeadeildo/ifood-sdk)
[![license](https://img.shields.io/badge/license-MIT-8ba69d)](LICENSE)

</div>

**Documentation: https://felipeadeildo.github.io/ifood-sdk/**

Login by OTP, read the order history, browse a menu, build a cart, place the order with Pix
and follow it until the delivery code. Every route was measured against the live service, and
`ifood.wire.endpoints` says which ones were confirmed and which are still guesses.

> **Not affiliated with iFood.** Independent client, built for study and personal use on your
> own account. It does not bypass authentication: you log in with your own phone and the code
> iFood sends. Read the [disclaimer](docs/disclaimer.md) first.

## Install

```bash
pip install ifood-sdk          # the client
pip install "ifood-sdk[mcp]"   # plus the MCP server
pip install "ifood-sdk[api]"   # plus the HTTP service
```

Not on PyPI yet: clone the repository and run `uv sync --all-extras`.

## Use it

```python
import ifood

client = ifood.Client(phone="+55 11 90000-0000", email="you@example.com")
client.login()               # the code arrives on WhatsApp
client.verify("123456")      # session saved under ~/.config/ifood-sdk/

order = client.orders.recent(1)[0]
print(order.number, order.status, order.merchant.name, order.delivery_code)
```

## What you get

| Capability | Call |
|---|---|
| OTP login, session saved on disk | `Client(phone=...).login().verify(code)` |
| Profile and saved addresses | `client.customers.profile()`, `client.customers.addresses()` |
| Place search and new address | `client.locations.search(query)`, `client.customers.add_address(...)` |
| Menu with prices and choices | `client.merchants.items(id, latitude=, longitude=)` |
| Order history, detail, timeline | `client.orders.recent()`, `get()`, `events()` |
| Repeat a past order | `client.orders.reorder(order, latitude=, longitude=)` |
| Cart build, create, edit | `client.carts.build/create/update_item/get` |
| Payment and checkout | `client.carts.set_payment_method()`, `place_order()` |
| Delivery code | `order.delivery_code` |

## Three ways to use it

```bash
python -m ifood.mcp                                          # agent tools over stdio
uvicorn ifood.api:build_app --factory --port 8000            # HTTP service with bearer
```

The MCP server and the HTTP service call the same operations from `ifood/ops.py`, so a fix
lands in both. The HTTP surfaces need a token: `IFOOD_MCP_TOKEN` and `IFOOD_API_TOKEN`.

## What it does not do

Grouped catalog and search sit behind PerimeterX and answer `EdgeBlocked`. Edge cookies last
minutes, so an old jar also comes back as `EdgeBlocked`. Details in
[limits](docs/reference/limits.md).

## Development

```bash
uv sync --all-groups --all-extras
uv run prek run --all-files      # ruff, ty and pytest
uv run zensical serve            # documentation on :8000
```

<div align="center">
  <img src="docs/assets/cat.svg" alt="adeildo" width="42" />
  <br />
  Brought to you by <a href="https://adeildo.dev">adeildo.dev</a>
</div>
