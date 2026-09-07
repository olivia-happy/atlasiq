from __future__ import annotations

import json
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from ..data import EVIDENCE, iso_now
from ..db import DecisionCardRecord, DecisionEvidenceSnapshotRecord, DecisionReviewRecord, session_scope
from ..schemas import DecisionCard, DecisionCardRequest, DecisionReview, DecisionReviewQueue, DecisionReviewRequest, DecisionReviewTrigger, DemoSeedResult, Evidence
from .news import acknowledge, list_news


CATEGORY_EVIDENCE_IDS = {
    "Policy": ["D3"],
    "Grid risk": ["D2"],
    "Demand": ["D1", "D2"],
}

DEMO_CARD_ID = "C-demo-grid"
DEMO_REVIEW_ID = "R-demo-grid"
EVIDENCE_BY_ID = {item["id"]: item for item in EVIDENCE}


def to_card(record: DecisionCardRecord) -> DecisionCard:
    return DecisionCard(
        id=record.id,
        title=record.title,
        verdict=record.verdict,
        rationale=record.rationale,
        evidence_ids=json.loads(record.evidence_json),
        owner=record.owner,
        review_date=record.review_date,
        created_at=record.created_at,
    )


def snapshot_evidence(session, card_id: str, evidence_ids: list[str]) -> None:
    for evidence_id in evidence_ids:
        evidence = EVIDENCE_BY_ID.get(evidence_id)
        if evidence is None:
            continue
        session.add(
            DecisionEvidenceSnapshotRecord(
                id=f"ES-{uuid4().hex[:10]}",
                decision_card_id=card_id,
                evidence_id=evidence_id,
                title=evidence["title"],
                source=evidence["source"],
                excerpt=evidence["excerpt"],
                metric=evidence["metric"],
            )
        )


def create_decision_card(request: DecisionCardRequest) -> DecisionCard:
    with session_scope() as session:
        record = DecisionCardRecord(
            id=f"C-{uuid4().hex[:10]}",
            title=request.title,
            verdict=request.verdict,
            rationale=request.rationale,
            evidence_json=json.dumps(request.evidence_ids),
            owner=request.owner,
            review_date=request.review_date,
            created_at=iso_now(),
        )
        session.add(record)
        session.flush()
        snapshot_evidence(session, record.id, request.evidence_ids)
        return to_card(record)


def to_review(record: DecisionReviewRecord) -> DecisionReview:
    return DecisionReview(
        id=record.id,
        decision_card_id=record.decision_card_id,
        outcome=record.outcome,
        note=record.note,
        created_at=record.created_at,
    )


def create_decision_review(card_id: str, request: DecisionReviewRequest) -> DecisionReview | None:
    with session_scope() as session:
        if session.get(DecisionCardRecord, card_id) is None:
            return None
        record = DecisionReviewRecord(
            id=f"R-{uuid4().hex[:10]}",
            decision_card_id=card_id,
            outcome=request.outcome,
            note=request.note,
            created_at=iso_now(),
        )
        session.add(record)
        session.flush()
        return to_review(record)


def list_decision_reviews(card_id: str) -> list[DecisionReview]:
    with session_scope() as session:
        records = session.scalars(
            select(DecisionReviewRecord)
            .where(DecisionReviewRecord.decision_card_id == card_id)
            .order_by(DecisionReviewRecord.created_at.desc())
        ).all()
        return [to_review(record) for record in records]


def list_evidence_snapshots(card_id: str) -> list[Evidence] | None:
    with session_scope() as session:
        if session.get(DecisionCardRecord, card_id) is None:
            return None
        records = session.scalars(
            select(DecisionEvidenceSnapshotRecord)
            .where(DecisionEvidenceSnapshotRecord.decision_card_id == card_id)
            .order_by(DecisionEvidenceSnapshotRecord.evidence_id)
        ).all()
    return [
        Evidence(id=record.evidence_id, title=record.title, source=record.source, excerpt=record.excerpt, metric=record.metric)
        for record in records
    ]


def build_decision_briefing(card_id: str) -> str | None:
    with session_scope() as session:
        record = session.get(DecisionCardRecord, card_id)
        if record is None:
            return None
        card = to_card(record)
        snapshots = session.scalars(
            select(DecisionEvidenceSnapshotRecord)
            .where(DecisionEvidenceSnapshotRecord.decision_card_id == card_id)
            .order_by(DecisionEvidenceSnapshotRecord.evidence_id)
        ).all()
    reviews = list_decision_reviews(card_id)
    evidence_lines = [f"- {evidence_id}" for evidence_id in card.evidence_ids] or ["- None recorded"]
    snapshot_lines = [
        f"### [{snapshot.evidence_id}] {snapshot.title}\n\n- Source: {snapshot.source}\n- Metric: {snapshot.metric}\n\n{snapshot.excerpt}\n"
        for snapshot in snapshots
    ] or ["- No evidence snapshot was recorded for this historical card."]
    lines = [
        "# AtlasIQ Decision Briefing",
        "",
        f"- Decision ID: {card.id}",
        f"- Verdict: {card.verdict}",
        f"- Owner: {card.owner}",
        f"- Review date: {card.review_date}",
        f"- Created at: {card.created_at}",
        "",
        "## Decision",
        "",
        f"### {card.title}",
        "",
        card.rationale,
        "",
        "## Evidence IDs",
        "",
        *evidence_lines,
        "",
        "## Evidence snapshot",
        "",
        *snapshot_lines,
        "",
        "## Review history",
        "",
    ]
    if not reviews:
        lines.append("- No manual review has been recorded.")
    else:
        for review in reviews:
            lines.extend([f"### {review.outcome} · {review.created_at}", "", review.note, ""])
    return "\n".join(lines)


def seed_demo_workspace() -> DemoSeedResult:
    created = False
    with session_scope() as session:
        record = session.get(DecisionCardRecord, DEMO_CARD_ID)
        if record is None:
            record = DecisionCardRecord(
                id=DEMO_CARD_ID,
                title="示例：德国光伏并网进入假设",
                verdict="watch",
                rationale="并网周期与政策支持是进入节奏的关键假设；确认新信号后需要由分析师复盘，而不是自动改变结论。",
                evidence_json=json.dumps(["D2", "D3"]),
                owner="Demo Strategy Desk",
                review_date=date.today().isoformat(),
                created_at=iso_now(),
            )
            session.add(record)
            snapshot_evidence(session, record.id, ["D2", "D3"])
            created = True
        if session.get(DecisionReviewRecord, DEMO_REVIEW_ID) is None:
            session.add(
                DecisionReviewRecord(
                    id=DEMO_REVIEW_ID,
                    decision_card_id=DEMO_CARD_ID,
                    outcome="maintain",
                    note="示例复盘：当前并网风险尚未被已确认信号推翻，维持观察并保留下一次复核入口。",
                    created_at=iso_now(),
                )
            )
        session.flush()
        card = to_card(record)
    acknowledge("N1")
    return DemoSeedResult(card=card, created=created)


def list_decision_cards() -> list[DecisionCard]:
    with session_scope() as session:
        records = session.scalars(select(DecisionCardRecord).order_by(DecisionCardRecord.created_at.desc())).all()
        return [to_card(record) for record in records]


def get_review_queue(today: date | None = None, upcoming_days: int = 7) -> DecisionReviewQueue:
    reference_date = today or date.today()
    upcoming_limit = reference_date + timedelta(days=upcoming_days)
    overdue: list[DecisionCard] = []
    due_today: list[DecisionCard] = []
    upcoming: list[DecisionCard] = []
    for card in list_decision_cards():
        review_date = date.fromisoformat(card.review_date)
        if review_date < reference_date:
            overdue.append(card)
        elif review_date == reference_date:
            due_today.append(card)
        elif review_date <= upcoming_limit:
            upcoming.append(card)
    return DecisionReviewQueue(
        overdue=sorted(overdue, key=lambda card: card.review_date),
        due_today=sorted(due_today, key=lambda card: card.review_date),
        upcoming=sorted(upcoming, key=lambda card: card.review_date),
    )


def get_review_triggers() -> list[DecisionReviewTrigger]:
    cards = list_decision_cards()
    triggers: list[DecisionReviewTrigger] = []
    for news in list_news():
        evidence_ids = CATEGORY_EVIDENCE_IDS.get(news.category, [])
        if not news.acknowledged or news.impact == "low" or not evidence_ids:
            continue
        related_cards = [card for card in cards if set(card.evidence_ids).intersection(evidence_ids)]
        if related_cards:
            triggers.append(
                DecisionReviewTrigger(
                    news=news,
                    evidence_ids=evidence_ids,
                    cards=related_cards,
                )
            )
    return triggers


def clear_decision_cards() -> None:
    with session_scope() as session:
        session.execute(delete(DecisionReviewRecord))
        session.execute(delete(DecisionEvidenceSnapshotRecord))
        session.execute(delete(DecisionCardRecord))
