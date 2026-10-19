"""Where the session is kept between runs.

The default is a JSON file under the user config directory. Anything that can read and
write a JSON document can replace it, so a Durable Object or a secret manager is a drop-in.
"""

import json
from pathlib import Path
from typing import Protocol

from ..wire.session import Session
from ..wire.settings import Settings, default_session_path


class SessionStore(Protocol):
    def load(self) -> Session | None: ...

    def save(self, session: Session) -> None: ...


class FileStore:
    """JSON file with owner-only permissions."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_session_path()

    def load(self) -> Session | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text())
        return Session(
            access_token=payload.get("access_token"),
            refresh_token=payload.get("refresh_token"),
            user_id=payload.get("user_id"),
            cookies=payload.get("cookies", {}),
            expires=payload.get("expires", {}),
        )

    def save(self, session: Session) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        session.save(self.path)


class MemoryStore:
    """Useful for tests and for callers that already hold the session."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    def load(self) -> Session | None:
        return self._session

    def save(self, session: Session) -> None:
        self._session = session


def default_store(settings: Settings | None = None) -> SessionStore:
    """The store used when the caller does not name one."""
    return FileStore((settings or Settings()).session_path)
