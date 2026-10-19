<div align="center">

<img src="docs/assets/logo.svg" width="72" height="72" alt="" />

# ifood-sdk

**Unofficial Python client for the iFood consumer API.**

[![Python 3.14](https://img.shields.io/badge/python-3.14-0e3b2e?style=flat-square)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-0e3b2e?style=flat-square)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-felipeadeildo.github.io-0e3b2e?style=flat-square)](https://felipeadeildo.github.io/ifood-sdk)
[![Unofficial](https://img.shields.io/badge/status-unofficial-64748b?style=flat-square)](#)

</div>

> **Not affiliated with iFood.** This is an independent, unofficial client, built for
> study and personal use on your own account. It does not bypass authentication: you log
> in with your own phone and the code iFood sends you. Read the
> [disclaimer](docs/disclaimer.md) before using it.

```bash
git clone https://github.com/felipeadeildo/ifood-sdk
cd ifood-sdk && uv sync --all-groups
```

```python
import ifood

client = ifood.Client(phone="+55 11 90000-0000")
client.login()              # the code arrives on WhatsApp
client.verify("123456")     # session saved to ~/.config/ifood-sdk/session.json

for order in client.orders.recent(3):
    print(order.number, order.status, order.merchant.name)
```

Next time, no login:

```python
import ifood

client = ifood.Client()
previous = client.orders.reorder(client.orders.recent(1)[0], latitude=-23.61, longitude=-46.67)
print(previous.merchant.name)
```

## What it does not do

Placing an order. `POST` and `PUT` on the iFood web API return a Cloudflare challenge for
any client whose TLS did not mint the session, and the mobile API requires device
attestation. The client builds and validates the cart payload locally, then stops. See
[limits](docs/reference/limits.md).

## Documentation

```bash
uv run zensical serve     # local site
```

Guides live in `docs/`: `install`, `login`, `orders`, `cart`, plus `reference` for
endpoints, errors and limits.

## Legal

Unofficial project, not affiliated with, endorsed by, or supported by iFood. Intended for
study and interoperability on your own account. The full text, including the limits of the
warranty, is in [docs/disclaimer.md](docs/disclaimer.md).

## Development

```bash
uv sync --all-groups
uv run prek run --all-files
```

`prek` runs ruff, ty and pytest from the project's own dependency group, so the machine
and CI use the same versions. Layout: `packages/sdk` is the client; `research` holds the
captures and the decompiled app, and is not versioned.


<br />

<div align="center">
<a href="https://adeildo.dev"><img src="https://adeildo.dev/assets/images/cat.svg" width="44" alt="A cat asleep on a laptop, the adeildo.dev logo"></a>
<br>
<sub>Brought to you by <a href="https://adeildo.dev">adeildo.dev</a></sub>
</div>
