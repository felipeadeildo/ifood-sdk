"""Where the client comes from at request time.

The session lives on disk, written by the login flow or exported by a browser. Neither the
MCP server nor the HTTP service keeps a client between requests, so a refreshed session is
picked up on the next call.
"""

from .client import Client


def get_client() -> Client:
    """Load the saved session. Tests replace this with a fake client."""
    return Client()
