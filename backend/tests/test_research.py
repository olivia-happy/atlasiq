import json

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import EvidenceItemInput, NewsItem, ResearchRun
from app.services.feature_store import save_evidence
from app.services.news import acknowledge, list_news, parse_gdelt_articles, parse_rss_articles, store_live_news
from app.services.research import summarize_research_runs


client = TestClient(app)


def test_research_stream_contains_citations() -> None:
    response = client.post("/api/research/ask", json={"question": "德国光伏市场的政策风险是什么？"})
    assert response.status_code == 200
    assert "event: citations" in response.text
    assert '"id": "DE-PACK"' in response.text


def test_research_stream_persists_an_auditable_runtime_record() -> None:
    question = "What policy risks matter for Germany photovoltaic market entry?"

    response = client.post("/api/research/ask", json={"question": question})

    assert response.status_code == 200
    done_payload = next(
        json.loads(block.splitlines()[1].removeprefix("data: "))
        for block in response.text.split("\n\n")
        if block.startswith("event: done\n")
    )
    assert done_payload["runtime"]["mode"] in {"ollama", "fallback"}
    assert done_payload["runtime"]["profile_id"] == "de"
    assert done_payload["runtime"]["latency_ms"] >= 0
    assert all(item.startswith("DE-") for item in done_payload["runtime"]["evidence_ids"])

    history = client.get("/api/research/runs")

    assert history.status_code == 200
    assert any(
        item["question"] == question
        and item["profile_id"] == "de"
        and all(evidence_id.startswith("DE-") for evidence_id in item["evidence_ids"])
        and item["mode"] in {"ollama", "fallback"}
        and item["answer"]
        for item in history.json()
    )


def test_research_stream_uses_the_selected_country_context_and_audits_it() -> None:
    response = client.post(
        "/api/research/ask",
        json={"question": "Saudi Arabia photovoltaic market entry: which risks need validation?", "profile_id": "sa"},
    )

    assert response.status_code == 200
    assert "Saudi Arabia" in response.text
    assert '"id": "SA-' in response.text
    done_payload = next(
        json.loads(block.splitlines()[1].removeprefix("data: "))
        for block in response.text.split("\n\n")
        if block.startswith("event: done\n")
    )
    assert done_payload["runtime"]["profile_id"] == "sa"
    assert any(item["profile_id"] == "sa" for item in client.get("/api/research/runs").json())


def test_research_observability_uses_nearest_rank_percentiles_and_evidence_coverage() -> None:
    runs = [
        ResearchRun(id="R1", question="q1", score=70, recommendation="持续观察", mode="ollama", model="qwen", latency_ms=10, evidence_ids=["D1"], created_at="2026-08-17T08:00:00+00:00"),
        ResearchRun(id="R2", question="q2", score=71, recommendation="持续观察", mode="fallback", model=None, latency_ms=20, evidence_ids=[], created_at="2026-08-17T08:01:00+00:00"),
        ResearchRun(id="R3", question="q3", score=72, recommendation="持续观察", mode="ollama", model="qwen", latency_ms=30, evidence_ids=["D1", "D3"], created_at="2026-08-17T08:02:00+00:00"),
        ResearchRun(id="R4", question="q4", score=73, recommendation="积极研究", mode="fallback", model=None, latency_ms=100, evidence_ids=["D3"], created_at="2026-08-17T08:03:00+00:00"),
    ]

    summary = summarize_research_runs(runs)

    assert summary.sample_size == 4
    assert summary.p50_latency_ms == 20
    assert summary.p95_latency_ms == 100
    assert summary.fallback_rate == 0.5
    assert summary.evidence_coverage == 0.75
    assert summary.last_run_at == "2026-08-17T08:03:00+00:00"


def test_research_observability_endpoint_exposes_quality_metrics() -> None:
    response = client.get("/api/research/observability")

    assert response.status_code == 200
    payload = response.json()
    assert {"sample_size", "p50_latency_ms", "p95_latency_ms", "fallback_rate", "evidence_coverage", "last_run_at"} <= set(payload)


def test_research_context_includes_profile_evidence_store_items() -> None:
    saved = save_evidence(
        "fr",
        [
            EvidenceItemInput(
                title="France grid auction signal",
                source="Public feed",
                url="https://example.test/fr-research-evidence",
                event_type="auction",
                impact_factors=["policy_auction"],
            )
        ],
    )[0]

    from app.services.research import evidence_for_profile

    evidence = evidence_for_profile("fr", "policy auction risk")

    assert any(item.id.endswith(saved.id) for item in evidence)
    assert any("unconfirmed" in item.excerpt.lower() for item in evidence)


def test_acknowledge_news_changes_item_state() -> None:
    response = client.post("/api/news/N1/acknowledge")
    assert response.status_code == 200
    assert response.json() == {"id": "N1", "acknowledged": True}


def test_parse_gdelt_articles_deduplicates_urls_and_classifies_policy_signal() -> None:
    payload = {
        "articles": [
            {
                "url": "https://example.com/policy",
                "title": "Germany changes solar subsidy rules",
                "seendate": "20260817T090000Z",
                "domain": "example.com",
            },
            {
                "url": "https://example.com/policy",
                "title": "Duplicate article",
                "seendate": "20260817T090100Z",
                "domain": "example.com",
            },
        ]
    }

    items = parse_gdelt_articles(payload)

    assert len(items) == 1
    assert items[0].category == "Policy"
    assert items[0].impact == "high"
    assert items[0].source == "example.com"


def test_parse_rss_articles_extracts_official_grid_signal() -> None:
    xml_text = """<?xml version='1.0'?>
    <rss><channel><item>
      <title>Grid connection update for renewable energy</title>
      <link>https://example.com/grid</link>
      <pubDate>Mon, 17 Aug 2026 09:00:00 GMT</pubDate>
      <description>Official electricity market update.</description>
    </item></channel></rss>"""

    items = parse_rss_articles(xml_text, "SMARD")

    assert len(items) == 1
    assert items[0].category == "Grid risk"
    assert items[0].source == "SMARD"


def test_live_news_is_persisted_and_can_be_acknowledged() -> None:
    item = NewsItem(
        id="R-persisted-grid",
        title="Grid connection rule update",
        category="Grid risk",
        impact="medium",
        summary="Persistent test signal.",
        why="Grid rules affect delivery timing.",
        source="SMARD",
        published_at="2026-08-17T09:00:00+00:00",
        acknowledged=False,
        url="https://example.com/persisted-grid",
    )

    stored = store_live_news([item])

    assert [news.id for news in stored] == ["R-persisted-grid"]
    assert next(news for news in list_news() if news.id == item.id).acknowledged is False
    assert acknowledge(item.id) is not None
    assert next(news for news in list_news() if news.id == item.id).acknowledged is True
