# ifood-sdk

Unofficial Python client for the iFood consumer API, built from measurements of the real
service rather than from documentation guesses. Source and issues live in
[felipeadeildo/ifood-sdk](https://github.com/felipeadeildo/ifood-sdk).

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

## What you can do

- Log in with a phone number. No password exists on the web client.
- Read the profile and the saved addresses.
- Read the order history, one order in detail, and its event timeline.
- Repeat a past order by asking for it with the delivery coordinates.
- Get the four digits the courier asks for.
- Build and validate a cart payload locally, without spending a request.

## What it does not do

Place the order. `POST` and `PUT` on the iFood web API answer a Cloudflare challenge to any
client whose TLS did not mint the session, and the mobile API requires device attestation.
The client stops at a validated payload. See [Limits](reference/limits.md).

Menu and search sit behind PerimeterX for the same kind of reason, so they are documented
as unavailable from plain HTTP.

## Next steps

- [Install](guides/install.md) the workspace and run the checks.
- [Log in](guides/login.md) and keep the session.
- [Read orders](guides/orders.md) and repeat the last one.
- [Build a cart](guides/cart.md) and see why sending it needs a browser.
- [Client reference](reference/client.md) for every method.

## Why measurements instead of assumptions

Each fact in this documentation names how it was established. An endpoint marked measured
was seen answering on the wire. One marked unknown was not, and the client either refuses
it or raises the edge error instead of pretending. The capture files and the decompiled app
live in `research/`, outside the published package.

<div align="center" markdown>
<a href="https://adeildo.dev"><img src="assets/cat.svg" width="44" alt="A cat asleep on a laptop, the adeildo.dev logo"></a>

<sub>Brought to you by <a href="https://adeildo.dev">adeildo.dev</a></sub>
</div>
