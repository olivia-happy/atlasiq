from app.schemas import EvidenceItemInput
from fastapi.testclient import TestClient
from app.main import app
from app.services.event_extraction import extract_event_fields
from app.services.feature_store import acknowledge_evidence, list_evidence, save_evidence
from app.schemas import NewsItem
from app.services.news import store_live_news


client = TestClient(app)


def test_grid_article_is_mapped_to_grid_factor_with_negative_direction() -> None:
    event = extract_event_fields(
        "Grid connection delay announced",
        "Projects face connection wait times.",
    )

    assert event.event_type == "grid"
    assert event.impact_factors == ["grid_absorption"]
    assert event.impact_direction == "negative"


def test_evidence_confirmation_is_profile_scoped_and_audited() -> None:
    evidence = save_evidence(
        "ae",
        [
            EvidenceItemInput(
                title="Auction capacity increases",
                source="Test source",
                url="https://example.test/ae-auction",
            )
        ],
    )[0]

    assert acknowledge_evidence("de", evidence.id) is None
    confirmed = acknowledge_evidence("ae", evidence.id)
    assert confirmed is not None
    assert confirmed.acknowledged is True


def test_storing_news_creates_a_country_scoped_extracted_evidence_record() -> None:
    store_live_news(
        [
            NewsItem(
                id="R-evidence-grid",
                title="Grid connection delay announced",
                category="Grid risk",
                impact="medium",
                summary="Projects face connection wait times.",
                why="Network capacity affects delivery timing.",
                source="Official RSS",
                published_at="2026-08-18T09:00:00+00:00",
                acknowledged=False,
                url="https://example.test/sa-grid-evidence",
            )
        ],
        "sa",
    )

    evidence = list_evidence("sa")

    assert len(evidence) == 1
    assert evidence[0].event_type == "grid"
    assert evidence[0].impact_factors == ["grid_absorption"]


def test_country_evidence_routes_are_scoped_and_allow_confirmation() -> None:
    evidence = save_evidence(
        "es",
        [
            EvidenceItemInput(
                title="Spain grid connection queue grows",
                source="Public feed",
                url="https://example.test/es-grid-route",
            )
        ],
    )[0]

    timeline = client.get("/api/countries/es/evidence/timeline")
    assert timeline.status_code == 200
    assert any(item["id"] == evidence.id for item in timeline.json())
    assert client.post(f"/api/countries/de/evidence/{evidence.id}/acknowledge").status_code == 404
    confirmed = client.post(f"/api/countries/es/evidence/{evidence.id}/acknowledge")
    assert confirmed.status_code == 200
    assert confirmed.json()["acknowledged"] is True
