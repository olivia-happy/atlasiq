from app.schemas import EvidenceItemInput, RawObservation
from app.services.feature_store import list_evidence, list_observations, save_evidence, save_observations


def test_observations_are_deduplicated_by_profile_source_metric_and_date() -> None:
    observation = RawObservation(
        profile_id="es",
        source_id="pvgis",
        metric_key="pv_yield",
        observed_at="2025",
        value=1700,
        unit="kwh_kw",
    )

    save_observations("es", [observation])
    save_observations("es", [observation])

    matching = [
        item
        for item in list_observations("es", "pv_yield")
        if item.observed_at == "2025"
    ]
    assert len(matching) == 1


def test_evidence_is_profile_scoped_and_caps_its_excerpt() -> None:
    evidence = save_evidence(
        "sa",
        [EvidenceItemInput(title="Saudi auction", source="RSS", url="https://example.test/auction", excerpt="x" * 1500)],
    )[0]

    assert evidence.profile_id == "sa"
    assert len(evidence.excerpt) == 1200
    assert list_evidence("de") == []
