import threading
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src import api
from src.models import AgentLogEntry, AgentSession


class FakeOrchestrator:
    release = threading.Event()

    def __init__(self, log_queue, cancel_event, **kwargs):
        self.log_queue = log_queue
        self.kwargs = kwargs

    def run(self, task):
        self.log_queue.put(AgentLogEntry(
            agent="system", message="STATE IDLE -> PLANNING", event_type="state_transition",
            from_state="IDLE", to_state="PLANNING",
        ))
        self.release.wait(5)
        self.log_queue.put(AgentLogEntry(agent="system", message="done", level="success"))
        return AgentSession(task=task, status="completed", final_code="print(1)")


@pytest.fixture
def client():
    api.jobs.clear()
    FakeOrchestrator.release.clear()
    with patch("src.api.Orchestrator", FakeOrchestrator):
        yield TestClient(api.app)
    FakeOrchestrator.release.set()


def test_job_lifecycle_streams_state_changes_over_sse(client):
    job_id = client.post("/jobs", json={"task": "print 1"}).json()["job_id"]
    FakeOrchestrator.release.set()

    with client.stream("GET", f"/jobs/{job_id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: state" in body and '"to_state": "PLANNING"' in body
    assert "event: log" in body
    assert body.rstrip().splitlines()[-2] == "event: end"
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["final_code"] == "print(1)"


def test_running_status_cancel_and_concurrency_limit(client):
    first = client.post("/jobs", json={"task": "a"}).json()["job_id"]
    client.post("/jobs", json={"task": "b"})
    assert client.post("/jobs", json={"task": "c"}).status_code == 429

    assert client.post(f"/jobs/{first}/cancel").status_code == 202
    assert api.jobs[first].cancel_event.is_set()
    assert client.get("/jobs/missing").status_code == 404


def test_rejects_invalid_input(client):
    assert client.post("/jobs", json={"task": ""}).status_code == 422
    assert client.post("/jobs", json={"task": "x", "max_retries": 99}).status_code == 422
    assert client.post("/jobs", json={"task": "x", "mode": "yolo"}).status_code == 422


def test_bearer_token_required_when_configured(client):
    with patch("src.api.API_TOKEN", "secret"):
        assert client.get("/jobs/x").status_code == 401
        headers = {"Authorization": "Bearer secret"}
        assert client.get("/jobs/x", headers=headers).status_code == 404
