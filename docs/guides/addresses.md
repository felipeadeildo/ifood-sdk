# Addresses

Three separate things share the word address, and keeping them apart avoids most of the
confusion in this flow.

| What | Where it lives | Call |
|---|---|---|
| Saved addresses | your account | `client.customers.addresses()` |
| Place search | the address service | `client.locations.search("Av. Paulista, 1000")` |
| Save a new address | your account | `client.customers.add_address(payload)` |

## List what is saved

```python
for address in client.customers.addresses():
    print(address.label or address.street_name, address.coordinates)
```

Each item carries `id`, `coordinates`, `streetName`, `streetNumber`, `neighborhood`,
`postalCode`, and the flags `favorite` and `active`.

## Search a place

Search turns text into candidates with coordinates. It needs no login, because it uses the
address application key rather than your token.

```python
for place in client.locations.search("Av. Paulista, 1000"):
    print(place["coordinates"], place.get("streetName"))
```

The first result is what the web client uses to fill the "street" and "number" fields.

## Save an address

The body is the same one the web client sends. Every field below was observed on the wire.

```python
address = client.customers.add_address({
    "city": "Sao Paulo",
    "state": "SP",
    "country": "BR",
    "streetName": "Av. Paulista",
    "streetNumber": "1000",
    "neighborhood": "Bela Vista",
    "coordinates": {"latitude": -23.5646946, "longitude": -46.6517849},
    "postalCode": "01310100",
    "provider": "GOOGLE",
})
```

## Selecting an address is not a request

Nothing on the server records "the address I chose". The selected address is client state,
and it travels inside the cart payload as the `address` field. That is why the cart builder
takes an address object (or a raw dict) and why `repeat()` reuses the address from the
previous order.

```python
saved = client.customers.addresses()[0]
payload = client.carts.build(
    merchant_id="...",
    address=saved,
    items=[...],
    account=client.account,
)
```

## What is not measured

Reverse geocoding (coordinates to address) is declared in `ifood.wire.endpoints` but was
never seen on the wire, so treat `client.locations.reverse()` as unverified.
