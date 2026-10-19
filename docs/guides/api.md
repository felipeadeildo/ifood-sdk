# HTTP service

`ifood-sdk[api]` ships a FastAPI app over the same operations the MCP server exposes.

```bash
IFOOD_API_TOKEN=secret uv run uvicorn ifood.api:build_app --factory
```

| Route | Returns |
|---|---|
| `GET /health` | liveness, no token needed |
| `GET /session` | whether the saved session works and how long the token lasts |
| `GET /orders?size=5` | recent orders |
| `GET /orders/{id}` | one order with items, fees and payment |
| `GET /orders/{id}/track` | status, arrival window, timeline, delivery code |
| `GET /addresses` | saved addresses with coordinates |
| `POST /orders/{id}/repeat` | validated cart payload plus what changed |

Everything except `/health` requires `Authorization: Bearer <IFOOD_API_TOKEN>`. With the
variable unset the service answers 503, so a forgotten token never leaves an open door.

The repeat route is a `POST` because it reads a past order and computes a payload; it does
not place anything. Sending the payload happens in the app, for the reason in
[Limits](../reference/limits.md).

## Authentication

A static bearer is the starting point. For a public deployment the next step is an OAuth
2.1 access token validated by a library, not by string comparison, and a per-user session
store instead of one file on disk.
