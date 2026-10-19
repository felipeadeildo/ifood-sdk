# ifood-sdk

Unofficial Python client for the iFood consumer API. The parts that work are measured
against the real service, and the parts that do not are documented instead of guessed.

Docs: https://felipeadeildo.github.io/ifood-sdk

```bash
git clone https://github.com/felipeadeildo/ifood-sdk
cd ifood-sdk
uv sync --all-groups
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

## Development

```bash
uv sync --all-groups
uv run prek run --all-files
```

`prek` runs ruff, ty and pytest from the project's own dependency group, so the machine
and CI use the same versions. Layout: `packages/sdk` is the client; `research` holds the
captures and the decompiled app, and is not versioned.
