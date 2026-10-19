# Quickstart

One script: log in, find a merchant, build a cart, place the order and read it back. The
identifiers below are placeholders; the comments say where each one comes from.

```python
import ifood

client = ifood.Client(phone="+55 11 90000-0000", email="you@example.com")
client.login()
client.verify("123456")          # session saved, next runs start with ifood.Client()

order = client.orders.recent(1)[0]
address = client.customers.addresses()[0]
merchant_id = order.merchant.id
latitude, longitude = address.coordinates.latitude, address.coordinates.longitude
```

`order.merchant.id` comes from the order history. The coordinates come from the saved
address, and the menu calls need them because delivery area and price depend on the point.

## Read the menu

```python
items = client.merchants.items(merchant_id, latitude=latitude, longitude=longitude)
dish = next(item for item in items if item["needChoices"] is False)
print(dish["description"], dish["unitPrice"])
```

This route returns the item list with prices and choice groups. The grouped catalog used by
the site is a different route and stays behind PerimeterX.

## Build the cart

```python
from ifood import CartItem

payload = client.carts.build(
    merchant=order.merchant,
    address=address,
    items=[CartItem(dish["id"], 1)],
    account=client.account,
)
cart = client.carts.create(payload)
print(cart.cart.id, cart.cart.total, cart.signature)
```

`build` is pure: it validates with the same codes the server uses, spends no network call
and refuses to mix the v1 and v2 contracts. `create` sends it and returns the snapshot with
the signature.

## Pay and place the order

```python
cart_id = cart.cart.id
client.carts.set_payment_method(cart_id, [{"id": "pix-method-id"}])
placed = client.carts.place_order(cart_id, cpf_cnpj="000.000.000-00")
print(placed.order_id, placed.pix_qr_code)
```

The payment method id comes from the cart snapshot. `place_order` reads the cart, builds the
checkout body and sends it. The order stays `CREATED` until the Pix is paid.

## Follow it

```python
detail = client.orders.get(placed.order_id)
print(detail.status, detail.delivery_code)

for event in client.orders.events(placed.order_id):
    print(event["timestamp"], event["value"])
```

The timeline moves from `CREATED` to `PLACED` when the payment lands, then `CONFIRMED` when
the merchant accepts. `DELIVERY_CODE` is the four digits you read to the courier.

## Next

- [Cart and checkout](cart.md) for the write path in detail.
- [Addresses](addresses.md) for search and saved places.
- [Limits](../reference/limits.md) for what still needs a browser.
