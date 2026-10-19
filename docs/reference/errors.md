# Errors

Callers never parse bodies. Every failure arrives as one of four types.

| Type | Meaning | Retry |
|---|---|---|
| `EdgeBlocked` | Cloudflare or PerimeterX refused before routing | no, refresh the session |
| `RateLimited` | 429 without `Retry-After` | yes, with jitter |
| `AuthMissing` | no bearer token, or a token the BFF refused | after login |
| `BusinessRule` | the request reached the service and a rule refused it | no |

The API answers in three shapes:

- flat: `{"code": "IFSL-2004", "message": "..."}`
- nested: `{"error": {"code": "CART-006", "message": "..."}}`
- kong: `{"message": "Not Found"}` for a route that does not exist

The mapping lives in `ifood.errors.from_response`. It checks the edge first, because an
HTML challenge can carry any status code, and the rate limit before the envelopes,
because 429 arrives in the same flat shape as a validation failure.
