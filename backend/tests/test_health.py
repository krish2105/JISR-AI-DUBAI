"""
test_health.py — Phase 0 acceptance: the API starts and `/health` answers.
"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_ok_and_fake_profile():
    """GET /health returns status ok and shows the fake models used in tests."""
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"
    assert body["llm_profile"] == "fake"
    # Every role is listed so an operator can see which model serves it.
    assert set(body["models"]) == {"smart", "worker", "fast", "judge", "stt"}
