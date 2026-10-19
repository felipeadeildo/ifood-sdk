# Orders and tracking

```python
order = client.orders.recent(1)[0]

print(order.number)               # 7782
print(order.status)               # CREATED, PLACED, CONFIRMED, ...
print(order.delivery_code)        # four digits for the courier
```

Payment is the `CREATED` to `PLACED` transition. There is no `PAYMENT_APPROVED` event, and
`CONFIRMED` means the store accepted the order, not that money moved.

## Reorder

```python
previous = client.orders.reorder(order, latitude=-23.61, longitude=-46.67)
print(previous.merchant.name, [item.name for item in previous.bag.items])
```

Coordinates are required. The returned sub-item ids belong to the catalog snapshot of
that order, so adding them to a cart needs the current menu to resolve option groups.
