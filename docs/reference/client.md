# Client

One class holds the session and the resources.

```python
import ifood

client = ifood.Client()                       # reuse the saved session
client = ifood.Client(phone="+55 11 ...")     # prepare a login
client = ifood.Client(jar="session.jar")      # session exported from a browser
```

## Login

| Method | What it does |
|---|---|
| `client.login(channel="WHATSAPP")` | sends the one-time code, returns the client |
| `client.verify("123456")` | exchanges the code, saves the session, returns the client |
| `client.logout()` | forgets the tokens in memory |
| `client.logged_in` | whether a token is present |

The code expires in 60 seconds and its key works once. `Client(phone=...)` accepts
`+55 11 90000-0000`, `(11) 90000-0000` or `5511900000000`.

## Resources

| Resource | Methods |
|---|---|
| `client.customers` | `profile()`, `addresses()`, `add_address()` |
| `client.locations` | `search()` |
| `client.orders` | `recent(size=5)`, `list(page, size)`, `get(id)`, `events(id)`, `reorder(order, latitude=, longitude=)`, `delivery_code(order)` |
| `client.merchants` | `get(id)`, `catalog(id, latitude=, longitude=)` |
| `client.carts` | `build(...)`, `create(payload)`, `set_payment_method`, `apply_voucher`, `remove_voucher`, `checkout(cart_id, payload)` |
| `client.vouchers` | `apply_to_cart`, `remove_from_cart` |

`recent`, `reorder` and `delivery_code` accept the `Order` object or its id.

## Models

Payloads come back as pydantic models. Unknown fields are kept, so `model_dump()` returns
whatever the API sent.

| Model | Useful attributes |
|---|---|
| `Order` | `number`, `status`, `merchant`, `delivery`, `bag`, `payments`, `delivery_code` |
| `Address` | `street_name`, `street_number`, `city`, `coordinates` |
| `CartResponse` | `cart`, `signature` |
| `CheckoutResult` | `order_id`, `pix_qr_code` |

## Building a cart

```python
from ifood import CartItem, SubItem

payload = client.carts.build(
    merchant=client.merchants.get(merchant_id),
    address=client.customers.addresses()[0],
    items=[CartItem("catalog-item-id", 1, SubItem("option-id"), observation=".")],
)
```

`merchant`, `address`, `items` and `account` take our objects or raw dicts. The account
defaults to the logged-in user, read from the profile once and reused.

The builder raises `CartPayloadError` with the code the server would return
(`CART-006`, `CART-007`) before any request is made.
