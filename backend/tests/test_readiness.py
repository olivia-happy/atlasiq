from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_decision_readiness_explains_evidence_freshness_and_audit_gaps() -> None:
    response = client.get("/api/decision-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert 0 <= payload["score"] <= 100
    assert payload["status"] in {"ready", "caution", "not_ready"}
    assert payload["next_action"]
    checks = {item["key"]: item for item in payload["checks"]}
    assert set(checks) == {"evidence", "source_freshness", "audit_trace"}
    assert {item["status"] for item in checks.values()} <= {"pass", "caution", "missing"}
