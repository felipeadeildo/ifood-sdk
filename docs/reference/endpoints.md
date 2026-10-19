# Endpoints

Every route the SDK uses, tagged by how it was established.

| Route | Method | Status |
|---|---|---|
| `/v4/identity-providers` | POST | measured |
| `/v2/identity-providers/OTP/authorization-codes` | POST | measured |
| `/v2/identity-providers/OTP/access-tokens` | POST | measured |
| `/v1/identity-providers/OTP/challenges` | POST | measured |
| `/v3/identity-providers/OTP/authentications` | POST | measured |
| `/v1/customers/me` | GET | measured |
| `/v1/customers/me/addresses` | GET | measured |
| `/v4/customers/me/orders` | GET | measured |
| `/v3/customers/me/orders/{id}` | GET | measured |
| `/v1/customers/me/orders/{id}/events` | GET | measured |
| `/v1/customers/me/orders/{id}/reorder` | GET | measured |
| `/v2/carts` | POST | measured |
| `/v2/carts/{id}/checkout` | POST | measured |
| `/v1/merchants/{id}` | GET | measured |
| `/v1/merchants/restaurant/{id}/catalog` | GET | menu, PerimeterX |
| `/v2/cardstack/search/results` | POST | unknown: only an edge 403 was seen |

Measured means observed on the wire. Unknown means assumed and unverified. Edge blocks do
not prove a route exists.
