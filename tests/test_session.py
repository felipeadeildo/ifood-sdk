import base64
import json
from pathlib import Path

from ifood import Session


def make_jwt(exp_offset: int = 7200) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS512"}').decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(json.dumps({"exp": 1_000_000 + exp_offset, "sub": "abc"}).encode())
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


def test_jar_is_parsed_and_checkout_secret_found(tmp_path: Path) -> None:
    jar = tmp_path / "session.jar"
    jar.write_text(
        "# Netscape HTTP Cookie File\n"
        ".ifood.com.br\tTRUE\t/\tTRUE\t0\taAccessToken\t" + make_jwt() + "\n"
        ".ifood.com.br\tTRUE\t/\tTRUE\t0\taDeviceId\tdev-1\n"
        ".ifood.com.br\tTRUE\t/\tTRUE\t0\tx-ifood-device-payment-abc\tsecret-64\n"
    )
    session = Session.from_jar(jar)
    assert session.has_user
    assert session.device_id == "dev-1"
    assert session.checkout_secret() == "secret-64"
    assert session.expires_in() is not None


def test_edge_status_reports_which_cookies_exist(tmp_path: Path) -> None:
    jar = tmp_path / "session.jar"
    jar.write_text(".ifood.com.br\tTRUE\t/\tTRUE\t0\t_px3\tv\n")
    status = Session.from_jar(jar).edge_status()
    assert status["_px3"] and not status["cf_clearance"]


def test_describe_reports_owner_and_remaining_seconds(tmp_path: Path) -> None:
    import time

    jar = tmp_path / "session.jar"
    future = int(time.time()) + 300
    jar.write_text(
        ".ifood.com.br\tTRUE\t/\tTRUE\t" + str(future) + "\tcf_clearance\tv\n"
        ".ifood.com.br\tTRUE\t/\tTRUE\t0\t_px3\tv\n"
    )
    described = {item["name"]: item for item in Session.from_jar(jar).describe()}
    assert described["cf_clearance"]["owner"] == "cloudflare"
    assert described["cf_clearance"]["seconds_left"] > 0
    assert described["_px3"]["owner"] == "perimeterx"
    assert described["_px3"]["present"] is True


def test_profile_absorbs_rotation_from_the_jar() -> None:
    from ifood.wire.config import profile_from_session

    session = Session(cookies={"aAppVersion": "9.999.0", "aFasterAppKey": "new-key"})
    profile = profile_from_session(session)
    assert profile.app_version.value == "9.999.0"
    assert profile.client_application_key.value == "new-key"
