# ifood-sdk

Unofficial Python client for the iFood consumer API. Every route here was measured against
the live service; where a route is unverified, the docs say so. Source and issues live in
[felipeadeildo/ifood-sdk](https://github.com/felipeadeildo/ifood-sdk).

```bash
pip install ifood-sdk          # the client
pip install "ifood-sdk[mcp]"   # plus the MCP server
pip install "ifood-sdk[api]"   # plus the HTTP service
```

```python
import ifood

client = ifood.Client(phone="+55 11 90000-0000")
client.login()               # the code arrives on WhatsApp
client.verify("123456")      # session saved under ~/.config/ifood-sdk/

order = client.orders.recent(1)[0]
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

All three share one implementation. The MCP tools and the HTTP routes call the same
operations, so behavior cannot drift between them.

## What you can do

- Log in with a phone number and the code iFood sends. The web client has no password.
- Read the profile, list saved addresses, search places, save a new address.
- Read the menu of a merchant, with prices and choice groups.
- Create a cart, change its items, set the payment method and place the order.
- Read the order back, follow its event timeline and get the delivery code.
- Repeat a past order with the coordinates of the delivery address.

## What it does not do

- Serve the grouped catalog or the search results. Both sit behind PerimeterX and answer
  `EdgeBlocked`.
- Guarantee a session. Edge cookies last minutes, so an old jar comes back as `EdgeBlocked`
  and the call has to wait for a fresh login.
- Charge anything on its own. A Pix order stays `CREATED` until someone pays the QR.

## How the project works

Routes carry a status in `ifood.wire.endpoints`: `measured` when a live call confirmed the
shape, `bundle` when it comes from the web bundle and was never called, `unknown` when it is
a guess. The [limits page](reference/limits.md) states what each one needs, so a call fails
with a reason instead of a surprise.

## Next steps

- [Quickstart](guides/quickstart.md): login to order in one script.
- [Cart and checkout](guides/cart.md): the write path, step by step.
- [MCP server](guides/mcp.md): the same operations as agent tools.
- [Client reference](reference/client.md): every method and model.
