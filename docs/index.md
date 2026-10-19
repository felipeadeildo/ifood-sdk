# ifood-sdk

Unofficial Python client for the iFood consumer API, built from measurements of the real
service rather than from documentation guesses. Source and issues live in
[felipeadeildo/ifood-sdk](https://github.com/felipeadeildo/ifood-sdk).

```bash
pip install ifood-sdk          # the client
pip install "ifood-sdk[mcp]"   # plus the MCP server
pip install "ifood-sdk[api]"   # plus the HTTP service
```

```python
import ifood

client = ifood.Client(phone="+55 11 90000-0000")
client.login()              # the code arrives on WhatsApp
client.verify("123456")     # session saved to ~/.config/ifood-sdk/session.json

for order in client.orders.recent(3):
    print(order.number, order.status, order.merchant.name)
```

!!! warning "Not affiliated with iFood"

    This is an independent client, built for study and personal use on your own account.
    It does not bypass authentication. Read the [disclaimer](disclaimer.md) before using it.

## Three ways to use it

| You want | Install | Entry point |
|---|---|---|
| a Python client | `ifood-sdk` | `ifood.Client` |
| tools for an agent | `ifood-sdk[mcp]` | `python -m ifood.mcp` |
| an HTTP service | `ifood-sdk[api]` | `uvicorn ifood.api:build_app --factory` |

All three share one implementation. The MCP server and the HTTP service call the same
operations, so a fix in one lands in the other.

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

- [Install](guides/install.md) with the extras you need.
- [Log in](guides/login.md) and keep the session.
- [Read orders](guides/orders.md) and repeat the last one.
- [Serve MCP](guides/mcp.md) to an agent.
- [Serve HTTP](guides/api.md) to other machines.
- [Client reference](reference/client.md) for every method.
