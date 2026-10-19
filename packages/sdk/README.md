# ifood-sdk

Unofficial Python client for the iFood consumer API. Python 3.14, `uv`, one runtime
dependency family (`httpx`, `pydantic`, `pydantic-settings`).

## Login

The web client has no password login: the account is identified, then a code arrives on
WhatsApp. The code is valid for 60 seconds and its key works once.

```python
import ifood

client = ifood.Client(phone="+55 82 99401-1841", email="you@example.com")
client.login()
client.verify("123456")
```

`login()` and `verify()` return the same client, so the three lines can be one if you
prefer. On success the session is saved to `~/.config/ifood-sdk/session.json`.

Next run:

```python
client = ifood.Client()
assert client.logged_in
```

## Orders

```python
for order in client.orders.recent(3):
    print(order.number, order.status, order.merchant.name)

order = client.orders.recent(1)[0]
print(order.delivery.estimated_time_of_arrival.delivers_at)
print(order.delivery_code)     # four digits for the courier

for event in client.orders.events(order.id):
    print(event["timestamp"], event["value"])
```

Payment is the `CREATED` to `PLACED` transition. `CONFIRMED` means the store accepted.

## Reorder

```python
previous = client.orders.reorder(order, latitude=-23.61, longitude=-46.67)
print(previous.merchant.name)
for item in previous.bag.items:
    print(item.name, item.quantity, item.sub_items)
```

Coordinates are required. The sub-item ids belong to that order's catalog snapshot, so a
cart needs the current menu to resolve option groups.

## Cart payload

```python
from ifood import Account, CartItem, SubItem

payload = client.carts.build(
    merchant_id="...",
    address=client.customers.addresses()[0].model_dump(by_alias=True),
    items=[CartItem("catalog-item-id", 1, SubItem("option-id"), observation=".")],
    account=Account("account-id", "Name", "you@example.com", 55, "11", "900000000"),
    version="v2",
)
```

The builder validates with the codes the server would return (`CART-006`, `CART-007`) and
spends no network call. Sending it is blocked: see `docs/reference/limits.md`.

## Errors

```python
from ifood import EdgeBlocked, RateLimited, AuthMissing, BusinessRule
```

`EdgeBlocked` means Cloudflare or PerimeterX refused before routing. `RateLimited` is a
429 with no `Retry-After`. `AuthMissing` is a missing or refused token. `BusinessRule`
means the request arrived and a domain rule refused it.

## What works without a browser

Login, profile, addresses, merchant detail, order history, reorder, tracking and the
delivery code. Menu, search and every write do not, for the reasons in
`docs/reference/limits.md`.
