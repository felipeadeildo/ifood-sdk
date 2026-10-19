from ifood import Session, Transport


def test_identity_headers_are_always_sent() -> None:
    session = Session(access_token="jwt", user_id="user-1", cookies={"aDeviceId": "dev-1"})
    headers = Transport(session).headers()
    for name in ("x-ifood-device-id", "x-client-application-key", "x-device-model", "app_version"):
        assert name in headers
    assert headers["authorization"] == "Bearer jwt"


def test_px_cookie_header_is_built_from_session() -> None:
    session = Session(cookies={"_px3": "a", "_pxhd": "b", "pxcts": "c"})
    header = Transport(session).headers()["x-px-cookies"]
    assert header.endswith(", true")
    assert "_px3=a" in header
