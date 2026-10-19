"""The HTTP service, tested through the app object. No server, no network."""

import pytest
from fastapi.testclient import TestClient

from ifood import runtime
from ifood.api import build_app

from .fakes import FakeClient


@pytest.fixture(autouse=True)
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "get_client", lambda: FakeClient())


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("IFOOD_API_TOKEN", "secret")
    return TestClient(build_app())


def test_health_needs_no_token(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_everything_else_needs_the_token(client: TestClient) -> None:
    assert client.get("/orders").status_code == 401
    ok = client.get("/orders", headers={"authorization": "Bearer secret"})
    assert ok.status_code == 200
    assert ok.json()[0]["orderNumber"] == "7782"


def test_track_returns_status_and_events(client: TestClient) -> None:
    response = client.get("/orders/order-1/track", headers={"authorization": "Bearer secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CONFIRMED"
    assert body["delivery_code"] == "1841"


def test_repeat_returns_a_payload_not_an_order(client: TestClient) -> None:
    response = client.post("/orders/order-1/repeat", headers={"authorization": "Bearer secret"})
    assert response.status_code == 200
    assert response.json()["merchant"] == "Pizza Prime"


def test_without_a_configured_token_the_service_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IFOOD_API_TOKEN", raising=False)
    response = TestClient(build_app()).get("/orders")
    assert response.status_code == 503
