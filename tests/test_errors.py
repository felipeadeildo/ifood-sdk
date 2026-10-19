from ifood import BusinessRule, EdgeBlocked, RateLimited
from ifood.errors import from_response


def test_three_envelopes_are_distinguished() -> None:
    nested = from_response(400, {"error": {"code": "CART-006", "message": "missing"}}, {})
    flat = from_response(400, {"code": "SCO-3000", "message": "lat/lon"}, {})
    kong = from_response(404, {"message": "Not Found"}, {})
    assert isinstance(nested, BusinessRule) and nested.envelope == "nested"
    assert isinstance(flat, BusinessRule) and flat.envelope == "flat"
    assert kong.envelope == "kong"


def test_edge_and_rate_limit_are_not_business_rules() -> None:
    edge = from_response(403, "<title>Just a moment</title>", {"cf-mitigated": "challenge"})
    limited = from_response(429, {"message": "API rate limit exceeded"}, {})
    assert isinstance(edge, EdgeBlocked)
    assert isinstance(limited, RateLimited)
