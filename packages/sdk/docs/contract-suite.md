# Contract suite and capture inventory

Two things live here, both offline by default:

1. **Contract suite** — everything already observed in the iFood API, pinned by
   real recorded cassettes (`tests/contract/`). It needs no network, no session
   and no credentials.
2. **Capture inventory** — reads a browser capture (`requests.jsonl`) and turns it
   into one cassette per route (`tests/support/`). No markdown reports are
   generated; the operator removed that on purpose.

This suite is not the client. Its job is to hold the *facts* the SDK and the MCP
are built against, so a wrong assumption fails a test instead of a purchase.

## Layout

```
tests/contract/            test modules (one per contract area)
tests/fixtures/            curated, PII-free contract facts (json)
tests/cassettes/           recorded exchanges: root = recorded by the suite,
                           inventory/ + inventory-cart/ = generated from captures
tests/support/             inventory (capture -> cassettes), measure (CLI), shape
tests/support/pending/     modules still waiting to be ported into src/ifood
docs/contract-suite.md     this file
```

## Running

```bash
uv run pytest                        # offline: replays cassettes only
uv run pytest --live                 # hits the network, compares shape to cassette
uv run pytest --record               # hits the network and re-records the cassette
uv run pytest --live --jar ~/.config/ifood-sdk/session.jar   # per-endpoint smoke
uv run python -m tests.support.measure <capture>/requests.jsonl --cassettes out/
```

The client waits 1.2 s between real calls (`MIN_INTERVAL`). There is no parallel
mode, on purpose.

`--record` and `--live` only touch cheap, login-free routes (geocode, `/ip`,
unknown merchant). Nothing in this suite creates a cart, places an order or pays.

## Rules the suite enforces

- **No test may depend on a fresh `_px3`.** The PerimeterX cookie is re-evaluated
  per path and per call: in one window it worked for `/v2/categories` and failed
  for `/v1/merchants/restaurant/{uuid}/catalog`. Smoke tests are per endpoint, and
  a 403 from the edge is reported as *blocked*, never as expected contract.
- **Offline by default.** A cassette miss fails loudly instead of silently calling
  the network.
- **Fail-closed redaction.** Query values are kept only for an allowlist of names
  (`channel`, `size`, `page`, `type`…); everything else becomes `<redacted>`, and
  long opaque values are redacted even outside that list.
- **Writes are not testable offline.** Every write verb returns
  `403 cf-mitigated: challenge` even with a valid jar, the browser UA and the
  checkout `origin`/`referer`. The mobile door is **Play Integrity attestation**,
  not an embedded HMAC key, so this is the state of the project, not a temporary
  gap. No write test may claim to be deterministic.
- **Every constant has provenance.** `WireProfile` records `source`,
  `derivation`, `sent_as` and `rotation` per value, and a test fails when the
  shipped bundle disagrees with the embedded constants.

## Measured facts

| route | observed | cassette / test |
|---|---|---|
| `logistics /location/v1/addresses:geocode` (full address) | 200, `rules[]` + `addresses[0].coordinates` | `test_geocode_full_address` |
| same, street only (no number) | 200, **fabricates `streetNumber`** (`"1559"` for Rua Augusta) | `test_geocode_street_only_returns_candidate` |
| same, garbage query | **404 `IFSL-2002`**, `details` leaks the provider (`HERE`) | `test_geocode_garbage_is_404_ifsl2002` |
| same, without `x-application-key` | **401 `IFSL-2004`**, also in `x-ifood-error-code` | `test_geocode_without_application_key_is_401` |
| `marketplace /v1/merchants/{uuid}?channel=IFOOD` | **404 `IFCS-2001`** | `test_merchant_unknown_uuid_is_404_ifcs2001` |
| same, without `channel` | **400 `IFCS-2000`** | `test_merchant_without_channel_is_400` |
| `consumer /ip` | 200 `{"ip": …}` (cassette anonymised) | `test_ip_returns_valid_address` |
| `consumer /v1/customers/me` | **404 Kong** — account routes live on the `www/site-api` BFF | `consumer-api_customers-me.json` |
| `marketplace` under burst | **429 `{"message":"API rate limit exceeded"}`**, no `Retry-After`, cleared in ~40 s | `marketplace-429.json` |
| OTP login chain (`/v4/identity-providers` → `/v2/…/OTP/authorization-codes` → `/v2/…/OTP/access-tokens` → `/v1/…/OTP/challenges` → `/v3/…/OTP/authentications`) | 201/201/200/201, `timeout_in_seconds: 60`, `key` single-use, JWT `exp-iat = 7200` | `test_identity.py` |
| `POST /v2/carts` | 201, `{cartResponse, signature, data, warning}`; `delivery.now` is **bool** in v2, **string** in v1 | `test_cart_payload.py` |
| `POST /v2/carts/{id}/checkout` | 201 `{orderId, pixQRCode, cartResponse}`; `cartRequest` is **JSON in a string** | `test_checkout_contract.py` |
| order tracking | `GET /v3/customers/me/orders/{id}` + `/v1/…/events`; payment is the `CREATED → PLACED` transition | `test_checkout_contract.py` |

Paths, verbs and body shapes for every route are declared in
`src/ifood/endpoints.py`, each with its own status (`measured`, `legacy`,
`unknown`). The `endpoints` module is the index; this document is the evidence.

## Two API generations of the cart

The same operation has two different payloads, and mixing them is the most
expensive mistake available:

| | v1 (`WSV3`) | v2 (`www/site-api`, current web) |
|---|---|---|
| items | `{id, quantity, garnish}` | `{id, quantity, observation, subItems[{id, quantity}]}` |
| `delivery.now` | string `"true"` | boolean `true` |
| required extras | — | `account`, `source`, `merchant.name` |

`subItems[].id` is the id of the option **in the current catalogue**; the
`choiceCode` from order history belongs to another layer and yields `ITEM-001`.
That is why the cart payload builder takes already-resolved ids and stays a pure
function, and why "reorder last week's burger" needs the menu once per item.

## Cart snapshots are signed and short-lived

`cartResponse` carries its own `expiresAt`, which is **last mutation + ~10.3 s**;
the web checks out 0.40 s after mutating the cart. The total to charge must be
read from the final snapshot, never from the number a human approved minutes
earlier — measured case: 31.89 approved, 37.89 charged after switching to
priority delivery.

`signature` comes from the server (top-level of the cart response) and is the same
value carried inside `cartRequest`; nothing is signed client-side.

## Session

The jar lives outside the repository (`~/.config/ifood-sdk/session.jar`, mode 600)
and is passed explicitly, never inherited from a live browser:

```bash
IFOOD_JAR=~/.config/ifood-sdk/session.jar uv run pytest --live
```

What degrades is the **bot score**, not a fixed TTL: the `cf_clearance` expiry in
the jar stayed long while reads started returning the challenge a few minutes
after automated traffic. The suite therefore calls it
`SESSION_DEGRADES_AFTER_MINUTES` and never schedules a refresh with it.
`Session.describe()` reports remaining seconds per edge cookie, so a degraded
session can be told apart from a changed API.
