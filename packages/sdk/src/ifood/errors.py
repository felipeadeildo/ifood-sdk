"""Errors raised by the SDK.

The API answers failures in three different shapes. Callers should never parse a body
to find out what happened, so every shape is normalised here.
"""

from dataclasses import dataclass
from typing import Any, Literal

Envelope = Literal["flat", "nested", "kong", "edge", "unknown"]


@dataclass(slots=True)
class IfoodError(Exception):
    message: str
    status: int = 0
    code: str | None = None
    envelope: Envelope = "unknown"
    details: tuple[str, ...] = ()

    def __str__(self) -> str:
        head = f"HTTP {self.status}" if self.status else "error"
        code = f" {self.code}" if self.code else ""
        return f"{head}{code}: {self.message}"


@dataclass(slots=True)
class EdgeBlocked(IfoodError):
    """Cloudflare or PerimeterX refused the request before routing.

    Retrying does not help. A fresher session does.
    """

    vendor: Literal["cloudflare", "perimeterx", "unknown"] = "unknown"


@dataclass(slots=True)
class RateLimited(IfoodError):
    """The gateway sent 429 without Retry-After. Back off with jitter."""


@dataclass(slots=True)
class AuthMissing(IfoodError):
    """No bearer token, or a token the BFF refused."""


@dataclass(slots=True)
class BusinessRule(IfoodError):
    """The request reached the service and a domain rule refused it."""


EDGE_MARKERS: dict[Literal["cloudflare", "perimeterx"], tuple[str, ...]] = {
    "cloudflare": ("Just a moment",),
    "perimeterx": ("px-captcha", "Access to this page has been denied"),
}


def from_response(status: int, body: Any, headers: dict[str, str]) -> IfoodError:
    """Turn an HTTP response into the specific error type.

    Order matters. The edge answers HTML with a 4xx that looks like a domain error, and
    a 429 arrives in the same flat envelope as a validation failure.
    """
    text = body if isinstance(body, str) else ""
    vendor = _edge_vendor(text, headers)
    if vendor is not None:
        return EdgeBlocked(f"{vendor} challenge", status, envelope="edge", vendor=vendor)
    if status == 429:
        return RateLimited("rate limited", status, envelope="flat")
    if isinstance(body, dict):
        return _from_body(body, status, headers)
    if status == 401:
        header_code = headers.get("x-ifood-error-code")
        return AuthMissing(
            str(body)[:200], status, code=header_code, details=(header_code,) if header_code else ()
        )
    return IfoodError(str(body)[:200], status)


def _edge_vendor(text: str, headers: dict[str, str]) -> Literal["cloudflare", "perimeterx"] | None:
    if headers.get("cf-mitigated") == "challenge":
        return "cloudflare"
    for vendor, markers in EDGE_MARKERS.items():
        if any(marker in text for marker in markers):
            return vendor
    return None


def _from_body(body: dict[str, Any], status: int, headers: dict[str, str]) -> IfoodError:
    nested = body.get("error")
    if isinstance(nested, dict):
        return BusinessRule(
            str(nested.get("message", "")), status, code=nested.get("code"), envelope="nested"
        )
    if body.get("message") == "Not Found" and "code" not in body:
        return IfoodError("route not found", status, envelope="kong")
    if "code" in body and "message" in body:
        return BusinessRule(str(body["message"]), status, code=body.get("code"), envelope="flat")
    if status == 401:
        header_code = headers.get("x-ifood-error-code")
        return AuthMissing(
            str(body)[:200], status, code=header_code, details=(header_code,) if header_code else ()
        )
    return IfoodError(str(body)[:200], status)
