"""JSON shape helpers for contract tests: type skeletons, not values."""


def json_shape(payload: object) -> object:
    """Nested dict of type names, so a contract can be asserted without values."""
    if isinstance(payload, dict):
        return {key: json_shape(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [json_shape(payload[0])] if payload else ["<empty>"]
    if isinstance(payload, bool):
        return "bool"
    if payload is None:
        return "null"
    return type(payload).__name__
