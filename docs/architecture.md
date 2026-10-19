# Architecture

## Three products

`sdk` holds the measured contract: routes, headers, retries, error envelopes, payload
shapes. `api` wraps it so other machines can call the flows without embedding Python.
`mcp` exposes the flows as tools for an agent.

The dependency direction is one way: `api` and `mcp` import `sdk`, never the reverse. The
SDK never imports a web framework.

## Why not write once and bind everywhere

Sharing an implementation across languages sounds cheaper than it is. The parts that
differ (HTTP stacks, error types, async models) are exactly the parts that matter, and a
shared core hides them behind a translation layer that fails in new ways.

The practical version of "one source" is one OpenAPI document generated from the Python
models, with generated TypeScript types for the worker. The behaviour stays in Python.

## If the MCP server runs on Cloudflare

Cloudflare's Agents SDK ships `McpAgent`, an MCP server backed by a Durable Object with
Streamable HTTP transport and WebSocket hibernation. That is the right host for session
state, because a session here is a jar that expires in minutes and must survive between
agent calls.

What it must not do is reimplement the client. Keep the worker to transport, session
storage and tool schemas, and let `ifood-api` do the calls. Two implementations of the
same wire contract is how the two drift.

## Session model

A browser mints the edge cookies once; the SDK reuses them for reads. Writes need the
browser that minted the session, because Cloudflare challenges any other TLS. That makes
a session keeper a requirement, not a convenience: it refreshes the jar and performs the
writes. Everything else stays plain HTTP.
