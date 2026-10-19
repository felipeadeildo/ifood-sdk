# Cart and checkout

A cart has four steps: build the payload, create it, change what you need, then place the
order. Only the last one creates an order, and only payment moves it forward.

## Build

```python
from ifood import CartItem, SubItem

payload = client.carts.build(
    merchant=order.merchant,                    # a Merchant, a dict or an id
    address=client.customers.addresses()[0],    # an Address or a dict
    items=[CartItem(item_id, 1, SubItem(option_id), observation="")],
    account=client.account,                     # comes from the session
)
```

`build` is pure. It validates locally with the codes the server would return
(`CART-006` for a missing field, `CART-007` for the wrong type, `ITEM-001` for an
unresolved complement) and spends no network call.

The ids are the ones the menu returns: `client.merchants.items(...)` gives the item `id`, and
each `choices[].garnishItens[].id` is a valid `SubItem` id.

The two API versions disagree on purpose. On v2 complements go in `items[].subItems`,
`delivery.now` is a boolean and the body carries `account` and `source`. On v1 complements go
in `items[].garnish`, `delivery.now` is the string `"true"` and `delivery.mode` exists.
Mixing them returns `CART-007`, which is why the version is an argument, not a guess.

## Create

```python
cart = client.carts.create(payload)     # 201
print(cart.cart.id, cart.cart.total, cart.signature)
```

The response carries the snapshot, the `signature` and a lease on the quote. The lease is
renewed by every mutation, which is why the web client mutates and checks out in the same
second.

Sending works while the session is fresh. A stale jar comes back as `EdgeBlocked`; the
method is never the problem.

## Change

```python
client.carts.update_item(cart_id, item_id, payload)     # quantity, options, note
client.carts.set_payment_method(cart_id, [{"id": pix_method_id}])
client.carts.apply_voucher(cart_id, payload)
client.carts.remove_voucher(cart_id)
```

The payment method id comes from the cart snapshot, not from a fixed list.

## Read back

```python
cart = client.carts.get(cart_id)
print(cart.cart.total, cart.signature)
```

Use this before checkout when a human approved a price. The total that gets charged is the
one in the snapshot, and it changes if the delivery method or the items change.

## Place the order

```python
placed = client.carts.place_order(cart_id, cpf_cnpj="000.000.000-00")
print(placed.order_id, placed.pix_qr_code)
```

`place_order` reads the cart, builds the 25 KB checkout body and sends it. Two parts of that
body are easy to get wrong: `cartRequest` is a JSON string holding the cart response, and the
signature appears twice, at the top and inside that string.

The order stays `CREATED` until the Pix is paid. Nothing is charged by placing it.

## What is not measured

Adding an item to an existing cart through the public route was only seen as a full item
update, so `update_item` sends what the site sends. If you need to append a new line, create
the cart with all the items.
