# Limits

## Writes need the browser that minted the session

`POST` and `PUT` on the BFF return `403 cf-mitigated: challenge` for any client whose TLS
did not mint the session. Measured with `httpx`, `curl_cffi` (chrome, chrome131) and
`tls_client` (chrome_120), all using a valid jar, the browser user agent, `sec-ch-ua`,
and the same origin. Reads on the same jar keep working.

The mobile API is not an escape: its routes answer `Request integrity check failed`, and
the app carries Play Integrity, which is device attestation rather than a key in the
binary.

Consequences:

- the SDK does not promise writes, and no test claims to write offline;
- `EdgeBlocked` is the honest result, and it names the vendor;
- a cart can be built and validated locally, but placing the order is a separate decision.

## Session lifetime

Edge cookies work for minutes, not hours. The `cf_clearance` expiry is long, but the bot
score falls and the challenge comes back. The project calls this degradation, not a TTL.

## Menu and search

Both sit behind PerimeterX and fail with `EdgeBlocked` unless the session was minted in a
browser. A 403 at the edge does not prove the route exists, so their status stays unknown.
