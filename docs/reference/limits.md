# Limits

## Writes depend on a fresh session

A `POST` or `PUT` succeeds while the edge cookies are fresh and fails with
`403 cf-mitigated: challenge` once they are not. The method is never the problem; the age of
the session is.

| Call | Fresh jar | After roughly forty minutes |
|---|---|---|
| `GET /site-api/v1/customers/me` | `200` | `200` |
| `POST /site-api/v2/carts` with a measured payload | `201`, cart id and signature | `403` challenge |
| `POST ca-marketplace.ifood.com.br/v2/carts` with the same JWT | `400` from validation, so the mobile host accepts the token | `401` without a token |

A cart created this way appears in the browser as the account's own cart, so the API and the
site share state.

## Session lifetime

Edge cookies are useful for minutes. The `cf_clearance` expiry looks generous, but the bot
score falls and the challenge comes back. The project treats this as degradation, not as a
fixed TTL, so the client reloads the jar from disk before each call and surfaces
`EdgeBlocked` when the jar is stale.

## Menu and search

The grouped catalog (`/v1/merchants/restaurant/{id}/catalog`) and search
(`/v2/cardstack/search/results`) sit behind PerimeterX and fail with `EdgeBlocked`.

Menu items are reachable another way: `GET /v1/customers/me/merchants/{id}/items` returns
the item list with prices and choice groups, and answers `200` with a fresh session. It
does not carry the section grouping that the catalog does.

The mobile catalog route answers `Request integrity check failed`, so it needs the app.

## Checkout

`POST /site-api/v2/carts/{id}/checkout` was verified once through the site with a real Pix
order. It has not been replayed from plain HTTP, so treat it as unverified in this client.
