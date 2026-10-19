# Endpoints

Every route the SDK uses, grouped by job and tagged by how it was established.

Status values: `measured` means a live call confirmed the shape, `blocked` means the edge
refuses it without the browser that minted the session, `unknown` means assumed and never
verified.

## Identity

| Route | Method | Status |
|---|---|---|
| `/v4/identity-providers` | POST | measured |
| `/v2/identity-providers/OTP/authorization-codes` | POST | measured |
| `/v2/identity-providers/OTP/access-tokens` | POST | measured |
| `/v1/identity-providers/OTP/challenges` | POST | measured |
| `/v3/identity-providers/OTP/authentications` | POST | measured |

## Account and addresses

| Route | Method | Status |
|---|---|---|
| `/v1/customers/me` | GET | measured |
| `/v1/customers/me/addresses` | GET | measured |
| `/v1/customers/me/addresses` | POST | measured |
| `/location/v1/addresses:geocode` (logistics host) | GET | measured |
| `/location/v1/coordinates:reverse-geocode` | GET | unknown |

## Merchants and menu

| Route | Method | Status |
|---|---|---|
| `/v1/merchants/{id}` (marketplace host) | GET | measured |
| `/v1/customers/me/merchants/{id}/items` | GET | measured |
| `/v1/merchants/restaurant/{id}/catalog` | GET | blocked, PerimeterX |
| `/v2/cardstack/search/results` | POST | blocked, PerimeterX |

The items route returns prices and choice groups. The catalog returns the same content
grouped into sections, and stays behind PerimeterX.

## Cart

| Route | Method | Status |
|---|---|---|
| `/v2/carts` | POST | measured |
| `/v2/carts/{id}` | GET | measured |
| `/v2/carts/{id}/items/{itemId}` | PUT | measured |
| `/v2/carts/{id}/paymentMethod` | PUT | measured |
| `/v2/carts/{id}/voucher` | PUT | bundle |
| `/v2/carts/{id}/checkout` | POST | measured |

## Orders

| Route | Method | Status |
|---|---|---|
| `/v4/customers/me/orders` | GET | measured |
| `/v3/customers/me/orders/{id}` | GET | measured |
| `/v1/customers/me/orders/{id}/events` | GET | measured |
| `/v1/customers/me/orders/{id}/reorder` | GET | measured |
