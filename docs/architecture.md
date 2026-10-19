# Architecture

## One distribution, three surfaces

`ifood-sdk` is a single package with extras:

- `ifood` is the client. It owns the measured wire contract: routes, headers, retries,
  error envelopes, payload shapes.
- `ifood.ops` holds the operations both surfaces expose, so there is one implementation.
- `ifood.mcp` is the MCP server, behind the `mcp` extra.
- `ifood.api` is the FastAPI service, behind the `api` extra.

The dependency direction is one way: `mcp` and `api` import `ops`, `ops` imports the
client, and the client imports nothing from either surface. The client never imports a web
framework.

## Why extras instead of separate packages

Three distributions mean three versions to keep in step and three import names to remember.
An extra keeps the base install small (`pip install ifood-sdk` pulls only `httpx`,
`pydantic` and `pydantic-settings`) while leaving one version number and one namespace.

## Why not generate the MCP server from the API spec

FastMCP can turn an OpenAPI document into MCP tools, and it is a good tool for wrapping a
service you did not write. Here it would replace seven tools with names, descriptions and
return shapes chosen for a generic client: `repeat_last_order` would become a `POST` with a
path parameter, and the warning about a diverged order would disappear into a payload.

The operations are the product, so they are named and typed by hand, and both surfaces are
thin wrappers over them.

## Session model

A browser mints the edge cookies once; the SDK reuses them for reads and writes. Writes need a
browser that minted the session, because Cloudflare challenges any other TLS. That is why
the surfaces stop at reading and at building a payload, and why a session keeper is a
requirement for anyone who wants to write, not a convenience.

## If the MCP server runs on Cloudflare

Cloudflare's Agents SDK ships `McpAgent`, an MCP server backed by a Durable Object with
Streamable HTTP transport and WebSocket hibernation. The worker should stay thin: hold the
session in the object and call the HTTP service. Two implementations of the same wire
contract is how the two drift.
