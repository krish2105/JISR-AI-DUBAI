"""
test_api.py — The vertical slice over HTTP, including the SSE event stream and org isolation.
"""

import time

from fastapi.testclient import TestClient

from app.api.runs import parse_sse
from app.main import create_app


def _wait_for_status(client: TestClient, run_id: str, wanted: set[str], timeout: float = 10.0) -> dict:
    """Poll GET /runs/{id} until the background run reaches one of the wanted statuses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] in wanted:
            return run
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} stuck in {run['status']}")


def test_demo_samples_endpoint():
    """The three built-in samples are offered to the demo page."""
    with TestClient(create_app()) as client:
        ids = [s["id"] for s in client.get("/demo/samples").json()]
    assert ids == ["en_brass_runners", "ar_gift_boxes", "en_doc_mismatch", "hostile_bank_change"]


def test_full_path_over_http_with_sse_and_audit():
    """POST /runs -> approval inbox -> approve -> SSE shows the whole story -> audit verifies."""
    with TestClient(create_app()) as client:
        run_id = client.post("/runs", json={"sample_id": "en_brass_runners"}).json()["run_id"]
        _wait_for_status(client, run_id, {"needs_approval"})

        [approval] = client.get("/approvals").json()
        assert approval["run_id"] == run_id and approval["status"] == "pending"
        decided = client.post(f"/approvals/{approval['id']}/approve", json={"note": "looks good"}).json()
        assert decided["status"] == "approved"
        assert client.post(f"/approvals/{approval['id']}/approve").status_code == 409   # no double approval

        events = parse_sse(client.get(f"/runs/{run_id}/events").text)
        kinds = [e["kind"] for e in events]
        assert kinds[0] == "run_started" and kinds[-1] == "done"
        assert "approval_needed" in kinds and "approval_decided" in kinds

        # Resuming from a sequence number only returns later events.
        later = parse_sse(client.get(f"/runs/{run_id}/events", params={"after": events[-3]["seq"]}).text)
        assert [e["seq"] for e in later] == [e["seq"] for e in events[-2:]]
        # A browser reconnect sends Last-Event-ID instead; it resumes the same way.
        reconnect = {"Last-Event-ID": str(events[-3]["seq"])}
        resumed = parse_sse(client.get(f"/runs/{run_id}/events", headers=reconnect).text)
        assert [e["seq"] for e in resumed] == [e["seq"] for e in events[-2:]]

        assert client.get("/audit/verify").json()["ok"] is True
        assert client.get("/audit").json()[0]["action"] == "message.sent_simulated"


def test_hostile_run_streams_a_blocked_event():
    """The trust moment over HTTP: blocked event in the stream, nothing in the inbox."""
    with TestClient(create_app()) as client:
        run_id = client.post("/runs", json={"sample_id": "hostile_bank_change"}).json()["run_id"]
        _wait_for_status(client, run_id, {"blocked"})
        kinds = [e["kind"] for e in parse_sse(client.get(f"/runs/{run_id}/events").text)]
        assert "blocked" in kinds and kinds[-1] == "done"
        assert client.get("/approvals").json() == []


def test_other_organisation_cannot_see_a_run():
    """Per-organisation isolation: another org gets 404 for runs, events and approvals."""
    with TestClient(create_app()) as client:
        run_id = client.post("/runs", json={"sample_id": "en_brass_runners"}).json()["run_id"]
        _wait_for_status(client, run_id, {"needs_approval"})
        other = {"X-Org-Id": "someone_else"}
        assert client.get(f"/runs/{run_id}", headers=other).status_code == 404
        assert client.get(f"/runs/{run_id}/events", headers=other).status_code == 404
        assert client.get("/approvals", headers=other).json() == []
        approval_id = client.get("/approvals").json()[0]["id"]
        assert client.post(f"/approvals/{approval_id}/approve", headers=other).status_code == 404


def test_post_runs_validates_input():
    """Empty message or unknown sample is rejected."""
    with TestClient(create_app()) as client:
        assert client.post("/runs", json={"message": "   "}).status_code == 422
        assert client.post("/runs", json={"sample_id": "nope"}).status_code == 404
