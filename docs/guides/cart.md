# Cart

The builder is pure: give it ids already resolved against the current catalog.

```python
from ifood import Account, CartItem, SubItem

payload = client.carts.build(
    merchant_id="...",
    merchant_name="Pizza Prime",
    address=client.customers.addresses()[0].model_dump(by_alias=True),
    items=[CartItem("catalog-item-id", 1, SubItem("option-id"), observation=".")],
    account=Account("account-id", "Name", "mail@example.com", 55, "11", "900000000"),
    version="v2",
)
```

Options go positionally, quantity and observation are keyword arguments. The builder
validates locally and spends no network call.

`logistics` note: the two API versions disagree on purpose. On v2 complements go in
`items[].subItems`, `delivery.now` is a boolean and the body carries `account` and
`source`. On v1 complements go in `items[].garnish`, `delivery.now` is the string `"true"`
and `delivery.mode` exists. Mixing them returns `CART-007`, which is why the version is a
required argument.

Sending it is a different matter: see [limits](../reference/limits.md).
