"""HTTP service over the same client the SDK exposes."""

from .app import build_app

__all__ = ["build_app"]
