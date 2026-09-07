from __future__ import annotations

import os
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./atlasiq.db")


def build_engine():
    url = database_url()
    options = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **options)


ENGINE = build_engine()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SubscriptionRecord(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    country: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(80))
    frequency: Mapped[str] = mapped_column(String(16))
    min_impact: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(40))


class DeliveryRecord(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    news_id: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(254))
    mode: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40))


class DecisionCardRecord(Base):
    __tablename__ = "decision_cards"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    verdict: Mapped[str] = mapped_column(String(16), index=True)
    rationale: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(80))
    review_date: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[str] = mapped_column(String(40))


class DecisionReviewRecord(Base):
    __tablename__ = "decision_reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    decision_card_id: Mapped[str] = mapped_column(ForeignKey("decision_cards.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(16), index=True)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class DecisionEvidenceSnapshotRecord(Base):
    __tablename__ = "decision_evidence_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    decision_card_id: Mapped[str] = mapped_column(ForeignKey("decision_cards.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(300))
    excerpt: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(String(80))


class ResearchRunRecord(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    profile_id: Mapped[str] = mapped_column(String(8), index=True, default="de")
    score: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16), index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    evidence_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class ResearchOutputRecord(Base):
    __tablename__ = "research_outputs"

    research_run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), primary_key=True)
    answer: Mapped[str] = mapped_column(Text)


class ResearchReportRecord(Base):
    __tablename__ = "research_reports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(8), index=True)
    market_pack_id: Mapped[str] = mapped_column(String(64))
    market_pack_version: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(String(32))
    markdown: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class ReportDeliveryRecord(Base):
    __tablename__ = "report_deliveries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("research_reports.id"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    mode: Mapped[str] = mapped_column(String(16), index=True)
    attachments_json: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class SourceAuditRecord(Base):
    __tablename__ = "source_audits"

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    last_checked_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_success_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    observation_label: Mapped[str] = mapped_column(String(160))


class MarketPackVersionRecord(Base):
    __tablename__ = "market_pack_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pack_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(160))
    country: Mapped[str] = mapped_column(String(80))
    sector: Mapped[str] = mapped_column(String(80))
    config_json: Mapped[str] = mapped_column(Text)
    change_note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class NewsRecord(Base):
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(64), index=True)
    impact: Mapped[str] = mapped_column(String(16), index=True)
    summary: Mapped[str] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    published_at: Mapped[str] = mapped_column(String(80), index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    url: Mapped[str | None] = mapped_column(String(1000), unique=True, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class RawObservationRecord(Base):
    __tablename__ = "raw_observations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(8), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    metric_key: Mapped[str] = mapped_column(String(80), index=True)
    observed_at: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class EvidenceRecord(Base):
    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(8), index=True)
    title: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
    language: Mapped[str] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    impact_direction: Mapped[str] = mapped_column(String(16))
    impact_factors_json: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    extraction_mode: Mapped[str] = mapped_column(String(16))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class FactorSnapshotRecord(Base):
    __tablename__ = "factor_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(8), index=True)
    market_pack_id: Mapped[str] = mapped_column(String(64))
    market_pack_version: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[str] = mapped_column(String(40), index=True)
    items_json: Mapped[str] = mapped_column(Text)


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    profile_id: Mapped[str] = mapped_column(String(8), index=True)
    stage: Mapped[str] = mapped_column(String(24), index=True)
    owner: Mapped[str] = mapped_column(String(80), index=True)
    capacity_mw: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_cod: Mapped[str | None] = mapped_column(String(10), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    updated_at: Mapped[str] = mapped_column(String(40), index=True)


class AdmissionAssessmentRecord(Base):
    __tablename__ = "admission_assessments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    profile_id: Mapped[str] = mapped_column(String(8), index=True)
    factor_snapshot_id: Mapped[str] = mapped_column(String(64), index=True)
    verdict: Mapped[str] = mapped_column(String(32), index=True)
    risk_level: Mapped[str] = mapped_column(String(16))
    blockers_json: Mapped[str] = mapped_column(Text)
    task_ids_json: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class DueDiligenceTaskRecord(Base):
    __tablename__ = "due_diligence_tasks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    profile_id: Mapped[str] = mapped_column(String(8), index=True)
    factor_key: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(240))
    priority: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    owner: Mapped[str] = mapped_column(String(80), index=True)
    due_date: Mapped[str] = mapped_column(String(10), index=True)
    evidence_ids_json: Mapped[str] = mapped_column(Text)
    assessment_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    updated_at: Mapped[str] = mapped_column(String(40), index=True)


def init_db() -> None:
    Base.metadata.create_all(bind=ENGINE)
    columns = {column["name"] for column in inspect(ENGINE).get_columns("research_runs")}
    if "profile_id" not in columns:
        with ENGINE.begin() as connection:
            connection.execute(text("ALTER TABLE research_runs ADD COLUMN profile_id VARCHAR(8) NOT NULL DEFAULT 'de'"))


@contextmanager
def session_scope() -> Iterator:
    init_db()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
