from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings
from app.store import REACTIONS_BY_IDEMPOTENCY, RECEIPTS_BY_IDEMPOTENCY, RUNS

client = TestClient(app)

def setup_function() -> None:
    RUNS.clear()
    RECEIPTS_BY_IDEMPOTENCY.clear()
    REACTIONS_BY_IDEMPOTENCY.clear()
    get_settings.cache_clear()

def _start_run() -> dict:
    response = client.post("/api/v1/runs", json={"use_ai": False})
    assert response.status_code == 201
    return response.json()

def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_demo_run_is_deterministic_and_approved() -> None:
    run = _start_run()
    assert run["portfolio"]["source"] == "synthetic-demo"
    assert len(run["bids"]) == 3
    assert run["risk_verdict"]["status"] == "approved"
    assert run["selected_bid_id"] == run["bids"][0]["id"]
    assert run["shadow"]["protection_delta"] != 0

def test_dry_run_is_idempotent() -> None:
    run = _start_run()
    key = "dryrun-demo-0001"
    first = client.post(f"/api/v1/runs/{run['run_id']}/execute", json={"mode": "dry_run", "idempotency_key": key})
    second = client.post(f"/api/v1/runs/{run['run_id']}/execute", json={"mode": "dry_run", "idempotency_key": key})
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["receipt_id"] == second.json()["receipt_id"]

def test_paper_execution_is_disabled_by_default() -> None:
    run = _start_run()
    client.post(f"/api/v1/runs/{run['run_id']}/execute", json={"mode": "dry_run", "idempotency_key": "dryrun-demo-0002"})
    response = client.post(f"/api/v1/runs/{run['run_id']}/execute", json={"mode": "paper", "idempotency_key": "paper-demo-0001"})
    assert response.status_code == 403

def test_reauction_marks_prior_ranking_stale() -> None:
    run = _start_run()
    response = client.post(f"/api/v1/runs/{run['run_id']}/reauction", json={"idempotency_key": "reauction-0001", "drift_pct": 6.0})
    assert response.status_code == 200
    assert response.json()["current_state"] == "reauction_required"

def test_sse_endpoint_emits_typed_events() -> None:
    run = _start_run()
    response = client.get(f"/api/v1/runs/{run['run_id']}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_event" in response.text
    assert "Risk Governor" in response.text

def test_unknown_run_is_404() -> None:
    assert client.get("/api/v1/runs/run-does-not-exist").status_code == 404
