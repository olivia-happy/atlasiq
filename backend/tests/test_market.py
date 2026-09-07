from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ScenarioRequest
from app.services.market import get_overview, run_scenario, sensitivity_analysis


client = TestClient(app)


def test_sensitivity_analysis_ranks_demand_and_grid_as_largest_default_drivers() -> None:
    result = sensitivity_analysis(ScenarioRequest())

    assert result.baseline_score == get_overview().score
    assert [item.key for item in result.items[:2]] == ["demand_change", "grid_risk_change"]
    assert result.items[0].impact >= result.items[-1].impact
    assert result.items[0].positive_delta > 0
    assert result.items[1].positive_delta < 0


def test_sensitivity_endpoint_returns_ranked_one_at_a_time_effects() -> None:
    response = client.post("/api/market/sensitivity", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["perturbation"] == 10
    assert payload["items"][0]["key"] == "demand_change"


def test_overview_has_explainable_weighted_score() -> None:
    overview = get_overview()
    assert overview.score == 74.1
    assert round(sum(item.weight for item in overview.components), 2) == 1.0
    assert len(overview.evidence) >= 2


def test_negative_subsidy_scenario_reduces_score() -> None:
    result = run_scenario(ScenarioRequest(subsidy_change=-20))
    assert result.delta < 0
    assert result.score < get_overview().score
    assert "不构成投资建议" in result.explanation


def test_overview_endpoint_returns_market_payload() -> None:
    response = client.get("/api/market/overview")
    assert response.status_code == 200
    assert response.json()["market"] == "德国光伏市场"
