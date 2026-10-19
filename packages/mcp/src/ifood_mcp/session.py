"""One place that decides which client the tools use.

The session lives on disk, written by the login flow or exported by a browser. Tools never
hold a client between calls, so a refreshed session is picked up on the next request.
"""

import ifood


def get_client() -> ifood.Client:
    """Load the saved session. Tests replace this with a fake client."""
    return ifood.Client()
