from app.schemas import RawObservation
from app.services import factors
from app.services.factors import build_factor_snapshot, get_impact_matrix
from app.services.feature_store import save_observations
from app.services.sources import clear_source_audits, list_public_sources


def test_factor_snapshot_reports_observed_and_insufficient_dimensions() -> None:
    save_observations("fr", [
        RawObservation(profile_id="fr", source_id="pvgis", metric_key="annual_irradiation", observed_at="2025", value=1600, unit="kwh_m2"),
        RawObservation(profile_id="fr", source_id="pvgis", metric_key="pv_yield", observed_at="2025", value=1450, unit="kwh_kw"),
        RawObservation(profile_id="fr", source_id="world-bank", metric_key="gdp_growth", observed_at="2024", value=1.1, unit="percent"),
    ])

    snapshot = build_factor_snapshot("fr")
    by_key = {item.key: item for item in snapshot.items}

    assert len(snapshot.items) == 8
    assert by_key["solar_resource"].status == "observed"
    assert by_key["supply_trade"].status == "insufficient"
    assert by_key["supply_trade"].coverage_ratio == 0


def test_impact_matrix_returns_the_latest_country_snapshot() -> None:
    build_factor_snapshot("sa")

    matrix = get_impact_matrix("sa")

    assert matrix.profile_id == "sa"
    assert len(matrix.items) == 8


def test_feature_refresh_keeps_pvgis_and_world_bank_source_audits(monkeypatch) -> None:
    clear_source_audits()
    profile_id = "es"

    def pvgis(_profile):
        return [RawObservation(profile_id=profile_id, source_id="pvgis", metric_key="pv_yield", observed_at="latest", value=1650, unit="kwh_kw")]

    def world_bank(_profile):
        return [RawObservation(profile_id=profile_id, source_id="world-bank", metric_key="gdp_growth", observed_at="2024", value=2.4, unit="percent")]

    monkeypatch.setattr(factors, "fetch_pvgis", pvgis)
    monkeypatch.setattr(factors, "fetch_world_bank", world_bank)

    factors.refresh_feature_sources(profile_id)
    source_by_id = {item.id: item for item in list_public_sources(profile_id)}

    assert source_by_id["pvgis"].status == "live"
    assert source_by_id["pvgis"].last_success_at is not None
    assert source_by_id["world-bank"].status == "live"
