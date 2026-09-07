from app.schemas import ScenarioRequest
from app.services.market import simulate_uncertainty


def test_uncertainty_simulation_returns_ordered_percentiles_and_threshold_probability() -> None:
    result = simulate_uncertainty(ScenarioRequest(subsidy_change=-20), iterations=600, seed=7)

    assert result.p10 <= result.p50 <= result.p90
    assert 0 <= result.probability_research <= 1
    assert result.iterations == 600
    assert result.p50 < 74.1
