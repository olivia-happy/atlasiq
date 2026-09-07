from datetime import date

from fastapi.testclient import TestClient

from app.data import NEWS_ITEMS
from app.main import app
from app.schemas import DecisionCardRequest, DecisionReviewRequest
from app.services.decisions import clear_decision_cards, create_decision_card, create_decision_review, get_review_queue, get_review_triggers, list_decision_cards, list_decision_reviews
from app.services.news import acknowledge


client = TestClient(app)


def test_decision_card_persists_verdict_reasoning_and_evidence() -> None:
    clear_decision_cards()
    created = create_decision_card(
        DecisionCardRequest(
            title="德国光伏市场进入判断",
            verdict="watch",
            rationale="政策确定性和并网风险仍需核验。",
            evidence_ids=["D1", "D3"],
            owner="Strategy Desk",
            review_date="2026-09-17",
        )
    )

    cards = list_decision_cards()

    assert cards[0].id == created.id
    assert cards[0].verdict == "watch"
    assert cards[0].evidence_ids == ["D1", "D3"]
    clear_decision_cards()


def test_review_queue_groups_overdue_today_and_next_seven_days() -> None:
    clear_decision_cards()
    for title, review_date in [
        ("逾期复盘", "2026-08-16"),
        ("今日复盘", "2026-08-17"),
        ("本周复盘", "2026-08-20"),
        ("未来复盘", "2026-08-30"),
    ]:
        create_decision_card(
            DecisionCardRequest(
                title=title,
                verdict="watch",
                rationale="用于验证复盘队列的日期边界。",
                review_date=review_date,
            )
        )

    queue = get_review_queue(today=date(2026, 8, 17))

    assert [card.title for card in queue.overdue] == ["逾期复盘"]
    assert [card.title for card in queue.due_today] == ["今日复盘"]
    assert [card.title for card in queue.upcoming] == ["本周复盘"]
    clear_decision_cards()


def test_review_queue_endpoint_returns_grouped_cards() -> None:
    clear_decision_cards()
    create_decision_card(
        DecisionCardRequest(
            title="今日需要复盘的判断",
            verdict="watch",
            rationale="验证 API 会向前端返回可直接展示的复盘队列。",
            review_date=date.today().isoformat(),
        )
    )

    response = client.get("/api/decision-cards/review-queue")

    assert response.status_code == 200
    payload = response.json()
    assert [card["title"] for card in payload["due_today"]] == ["今日需要复盘的判断"]
    assert payload["overdue"] == []
    clear_decision_cards()


def test_confirmed_grid_signal_triggers_review_for_cards_using_grid_evidence() -> None:
    clear_decision_cards()
    NEWS_ITEMS[0]["acknowledged"] = False
    create_decision_card(
        DecisionCardRequest(
            title="验证并网假设",
            verdict="watch",
            rationale="并网周期会影响项目的交付节奏，需要在出现新信号后重新审视。",
            evidence_ids=["D2"],
            review_date="2026-08-20",
        )
    )
    acknowledge("N1")

    triggers = get_review_triggers()

    assert len(triggers) == 1
    assert triggers[0].news.id == "N1"
    assert triggers[0].evidence_ids == ["D2"]
    assert [card.title for card in triggers[0].cards] == ["验证并网假设"]
    NEWS_ITEMS[0]["acknowledged"] = False
    clear_decision_cards()


def test_review_triggers_endpoint_returns_confirmed_signal_and_related_cards() -> None:
    clear_decision_cards()
    NEWS_ITEMS[0]["acknowledged"] = False
    create_decision_card(
        DecisionCardRequest(
            title="并网周期需要复核",
            verdict="watch",
            rationale="将并网风险作为进入节奏的关键假设，在新信号出现后复核。",
            evidence_ids=["D2"],
            review_date="2026-08-20",
        )
    )
    acknowledge("N1")

    response = client.get("/api/decision-cards/review-triggers")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["news"]["id"] == "N1"
    assert [card["title"] for card in payload[0]["cards"]] == ["并网周期需要复核"]
    NEWS_ITEMS[0]["acknowledged"] = False
    clear_decision_cards()


def test_review_record_persists_and_is_returned_for_its_card() -> None:
    clear_decision_cards()
    card = create_decision_card(
        DecisionCardRequest(
            title="并网风险判断",
            verdict="watch",
            rationale="将并网周期作为进入节奏的关键假设，并在出现新信号后复核。",
            evidence_ids=["D2"],
            review_date="2026-08-20",
        )
    )

    created = create_decision_review(
        card.id,
        DecisionReviewRequest(outcome="maintain", note="并网风险尚未恶化，维持观察并等待下一轮公开数据。"),
    )

    reviews = list_decision_reviews(card.id)

    assert created is not None
    assert reviews[0].id == created.id
    assert reviews[0].decision_card_id == card.id
    assert reviews[0].outcome == "maintain"
    clear_decision_cards()


def test_review_endpoint_creates_record_and_rejects_unknown_card() -> None:
    clear_decision_cards()
    card = create_decision_card(
        DecisionCardRequest(
            title="政策假设复盘",
            verdict="watch",
            rationale="政策支持机制是市场进入节奏的重要前提，需要记录人工复盘。",
            evidence_ids=["D3"],
            review_date="2026-08-20",
        )
    )

    response = client.post(
        f"/api/decision-cards/{card.id}/reviews",
        json={"outcome": "adjust", "note": "政策假设发生变化，需要调整下一阶段的进入节奏。"},
    )
    missing = client.post(
        "/api/decision-cards/C-missing/reviews",
        json={"outcome": "retire", "note": "证据不足，停止跟踪该市场进入判断。"},
    )
    history = client.get(f"/api/decision-cards/{card.id}/reviews")

    assert response.status_code == 200
    assert response.json()["outcome"] == "adjust"
    assert missing.status_code == 404
    assert history.status_code == 200
    assert history.json()[0]["id"] == response.json()["id"]
    clear_decision_cards()


def test_briefing_endpoint_exports_card_and_review_history_as_markdown() -> None:
    clear_decision_cards()


def test_evidence_snapshot_endpoint_returns_saved_evidence_content() -> None:
    clear_decision_cards()
    card = create_decision_card(
        DecisionCardRequest(
            title="Snapshot lookup",
            verdict="watch",
            rationale="Persist the reviewed evidence content with this decision.",
            evidence_ids=["D2"],
            review_date="2026-08-20",
        )
    )

    response = client.get(f"/api/decision-cards/{card.id}/evidence-snapshot")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "D2"
    assert response.json()[0]["title"] == "Demand and grid-context indicator"
    clear_decision_cards()
    card = create_decision_card(
        DecisionCardRequest(
            title="Market entry hypothesis",
            verdict="watch",
            rationale="Grid connection timing remains the main execution assumption for this market entry.",
            evidence_ids=["D2", "D3"],
            review_date="2026-08-20",
        )
    )
    create_decision_review(
        card.id,
        DecisionReviewRequest(outcome="maintain", note="No verified signal has invalidated the grid timing assumption."),
    )

    response = client.get(f"/api/decision-cards/{card.id}/briefing")
    missing = client.get("/api/decision-cards/C-missing/briefing")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# AtlasIQ Decision Briefing" in response.text
    assert "Market entry hypothesis" in response.text
    assert "Demand and grid-context indicator" in response.text
    assert "variability remains a material execution risk" in response.text
    assert "maintain" in response.text
    assert missing.status_code == 404
    clear_decision_cards()


def test_demo_seed_creates_a_repeatable_review_workflow() -> None:
    clear_decision_cards()
    NEWS_ITEMS[0]["acknowledged"] = False

    first = client.post("/api/demo/seed")
    second = client.post("/api/demo/seed")

    assert first.status_code == 200
    assert second.status_code == 200
    card_id = first.json()["card"]["id"]
    cards = client.get("/api/decision-cards")
    reviews = client.get(f"/api/decision-cards/{card_id}/reviews")
    triggers = client.get("/api/decision-cards/review-triggers")
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert len(cards.json()) == 1
    assert len(reviews.json()) == 1
    assert triggers.json()[0]["news"]["id"] == "N1"
    NEWS_ITEMS[0]["acknowledged"] = False
    clear_decision_cards()
