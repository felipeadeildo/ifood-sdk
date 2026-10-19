# Cart and checkout, as measured

## Create (`POST /site-api/v2/carts`)

```json
{
  "merchant": {"id": "<uuid>", "name": "<merchant name>"},
  "address": {
    "id": "<saved address uuid>",
    "coordinates": {"latitude": -23.5646946, "longitude": -46.6517849},
    "streetName": "Av. Paulista", "streetNumber": "1000",
    "neighborhood": "Bela Vista", "state": "SP", "city": "Sao Paulo", "zipCode": "01310100"
  },
  "items": [{
    "id": "<catalog item id>", "quantity": 1, "observation": ".",
    "subItems": [{"id": "<option id>", "quantity": 1}]
  }],
  "delivery": {"id": "DEFAULT", "now": true, "deliveryBy": "IFOOD"},
  "account": {"id": "<uuid>", "name": "…", "email": "…",
              "phone": {"countryCode": 55, "areaCode": "11", "number": "…"}},
  "source": {"name": "web", "platform": "desktop", "requester": "ifood",
             "parameters": [{"name": "version", "value": "9.178.5"}]}
}
```

On v2 `delivery.now` is a boolean; on v1 it is the string "true". Do not unify them.

## Checkout (`POST /site-api/v2/carts/{cartId}/checkout`)

```json
{
  "paymentSources": {
    "sources": [{
      "source": "TOKEN",
      "paymentMethod": {"id": "…", "code": "1", "name": "PIX",
                        "method": {"name": "PIX"}, "brand": {"name": "PIX"},
                        "liability": "IFOOD", "type": {"name": "ONLINE"}},
      "amount": {"value": 37.89, "currency": "BRL"},
      "additionalData": {}
    }],
    "contextInfo": {"tags": "delivered_by_ifood",
                    "cybersourceFingerprint": "…", "clearsaleFingerprint": "…"}
  },
  "cpfCnpj": "…",
  "signature": "<same signature as the cart response>",
  "cartRequest": "<JSON string containing {\"cartResponse\": {...}}>"
}
```

- `cartRequest` must be a string. An object fails validation.
- `amount.value` mirrors the final `cartResponse` total. It changes when the customer
  switches the delivery method after seeing the price, so read it from the last cart
  response, never from what the customer approved earlier.
- Response `201`: `{orderId, pixQRCode, cartResponse}`.

## Tracking

- `GET /site-api/v3/customers/me/orders/{id}` → `lastStatus`, ETA, `payments`, `bag`.
- `GET /site-api/v1/customers/me/orders/{id}/events` → `CREATED → PLACED → CONFIRMED →
  DELIVERY_REQUEST_CREATED → ENABLE_TIP → DELIVERY_CREATED → DELIVERY_REQUEST_IN_PROGRESS`.
- Payment is the `CREATED → PLACED` transition. There is no `PAYMENT_APPROVED` event, and
  `CONFIRMED` means the store accepted, not that money moved.
