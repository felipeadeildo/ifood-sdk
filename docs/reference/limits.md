# Limits

## Writes work while the session is fresh

An earlier version of this page said writes need the browser that minted the session.
That was wrong, and the mistake is documented here on purpose.

What happened: writes were tested against a jar that had been open for about forty
minutes. Reads still worked, `POST` returned `403 cf-mitigated: challenge`, and the
conclusion was "the edge blocks writes". With a session minted minutes earlier, the same
`curl` `POST /site-api/v2/carts` returned `201` and the browser showed the cart as its own.
The 403 measured session degradation, not the HTTP method.

Measured now, with a fresh jar:

| Call | Result |
|---|---|
| `GET /site-api/v1/customers/me` | `200` |
| `POST /site-api/v2/carts` with the payload from a real order | `201`, cart id and signature returned |
| `POST ca-marketplace.ifood.com.br/v2/carts` with the same JWT | `400` from validation, so the mobile host accepts the token |

What still holds:

- the useful life of the edge cookies is minutes, so a long-running process must be able to
  reload the jar from disk;
- `EdgeBlocked` remains the honest error when the session is stale, and it names the vendor;
- the mobile catalog route answers `Request integrity check failed`, so that specific route
  still needs the app;
- checkout over HTTP was not re-verified after this correction.

## Session lifetime

Edge cookies work for minutes, not hours. The `cf_clearance` expiry is long, but the bot
score falls and the challenge comes back. The project calls this degradation, not a TTL.

## Menu and search

Both sit behind PerimeterX and fail with `EdgeBlocked` unless the session was minted in a
browser. A 403 at the edge does not prove the route exists, so their status stays unknown.
