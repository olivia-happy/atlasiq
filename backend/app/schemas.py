from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MetricPoint(BaseModel):
    month: str
    opportunity: float
    capacity_gw: float
    demand_index: float


class ScoreComponent(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    explanation: str


class Evidence(BaseModel):
    id: str
    title: str
    source: str
    excerpt: str
    metric: str


class MarketOverview(BaseModel):
    market: str
    score: float
    recommendation: str
    last_updated: str
    components: list[ScoreComponent]
    metrics: list[MetricPoint]
    evidence: list[Evidence]


class ScenarioRequest(BaseModel):
    subsidy_change: float = Field(default=0, ge=-60, le=60)
    demand_change: float = Field(default=0, ge=-40, le=40)
    grid_risk_change: float = Field(default=0, ge=-40, le=40)
    weather_change: float = Field(default=0, ge=-30, le=30)


class ScenarioResult(BaseModel):
    score: float
    delta: float
    recommendation: str
    component_scores: list[ScoreComponent]
    explanation: str


class SimulationResult(BaseModel):
    iterations: int
    p10: float
    p50: float
    p90: float
    probability_research: float
    explanation: str


class SensitivityItem(BaseModel):
    key: str
    label: str
    positive_delta: float
    negative_delta: float
    impact: float


class SensitivityResult(BaseModel):
    baseline_score: float
    perturbation: float
    items: list[SensitivityItem]


class ResearchRequest(BaseModel):
    question: str = Field(min_length=8, max_length=500)
    scenario: ScenarioRequest | None = None
    profile_id: Literal["de", "es", "fr", "ae", "sa"] = "de"


class ResearchRuntime(BaseModel):
    id: str
    profile_id: str = "de"
    mode: Literal["ollama", "fallback"]
    model: str | None
    latency_ms: int
    evidence_ids: list[str]
    created_at: str


class ResearchRun(ResearchRuntime):
    question: str
    score: float
    recommendation: str
    answer: str | None = None


class ResearchObservability(BaseModel):
    sample_size: int
    p50_latency_ms: int | None
    p95_latency_ms: int | None
    fallback_rate: float | None
    evidence_coverage: float | None
    last_run_at: str | None


class DecisionReadinessCheck(BaseModel):
    key: Literal["evidence", "source_freshness", "audit_trace"]
    label: str
    status: Literal["pass", "caution", "missing"]
    detail: str
    score: int
    max_score: int


class DecisionReadiness(BaseModel):
    score: int
    status: Literal["ready", "caution", "not_ready"]
    next_action: str
    checks: list[DecisionReadinessCheck]


class NewsItem(BaseModel):
    id: str
    title: str
    category: str
    impact: Literal["low", "medium", "high"]
    summary: str
    why: str
    source: str
    published_at: str
    acknowledged: bool
    url: str | None = None


class NewsRefreshResult(BaseModel):
    status: Literal["live", "degraded"]
    added: int
    message: str
    notifications_previewed: int = 0
    notifications_sent: int = 0


class NewsPollingStatus(BaseModel):
    enabled: bool
    interval_seconds: int


class AcknowledgeResult(BaseModel):
    id: str
    acknowledged: bool


class EmailPreviewRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class EmailPreviewResult(BaseModel):
    mode: Literal["preview", "sent"]
    subject: str
    message: str


class SubscriptionRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    country: str = Field(default="Germany", min_length=2, max_length=80)
    topic: str = Field(default="photovoltaic", min_length=2, max_length=80)
    frequency: Literal["immediate", "daily"] = "immediate"
    min_impact: Literal["medium", "high"] = "medium"

    @field_validator("email")
    @classmethod
    def valid_email_shape(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("A valid email address is required")
        return cleaned


class Subscription(SubscriptionRequest):
    id: str
    created_at: str


class NotificationDelivery(BaseModel):
    id: str
    subscription_id: str
    news_id: str
    email: str
    mode: Literal["preview", "sent", "failed"]
    message: str
    created_at: str


class DecisionCardRequest(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    verdict: Literal["research", "watch", "hold"]
    rationale: str = Field(min_length=8, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)
    owner: str = Field(default="Strategy Desk", min_length=2, max_length=80)
    review_date: str = Field(min_length=10, max_length=10)


class DecisionCard(DecisionCardRequest):
    id: str
    created_at: str


class DecisionReviewQueue(BaseModel):
    overdue: list[DecisionCard]
    due_today: list[DecisionCard]
    upcoming: list[DecisionCard]


class DecisionReviewTrigger(BaseModel):
    news: NewsItem
    evidence_ids: list[str]
    cards: list[DecisionCard]


class DecisionReviewRequest(BaseModel):
    outcome: Literal["maintain", "adjust", "retire"]
    note: str = Field(min_length=8, max_length=1000)


class DecisionReview(DecisionReviewRequest):
    id: str
    decision_card_id: str
    created_at: str


class DemoSeedResult(BaseModel):
    card: DecisionCard
    created: bool


class PublicDataSource(BaseModel):
    id: str
    profile_id: str = "de"
    name: str
    kind: Literal["energy", "weather"]
    refresh_mode: Literal["manual", "scheduled"]
    status: Literal["seed", "ready", "live", "degraded"]
    note: str
    last_checked_at: str | None = None
    last_success_at: str | None = None
    observation_label: str


class OwidGermanySnapshot(BaseModel):
    country: str
    records: int
    latest_year: int
    solar_capacity_gw: float | None
    solar_electricity_twh: float


class WeatherSnapshot(BaseModel):
    days: int
    average_temperature_c: float
    average_radiation_mj_m2: float


class DataRefreshResult(BaseModel):
    status: Literal["live", "degraded"]
    owid: OwidGermanySnapshot | None = None
    weather: WeatherSnapshot | None = None
    message: str


class MarketPackSummary(BaseModel):
    id: str
    version: int
    status: Literal["draft", "published", "archived"]
    name: str
    country: str
    sector: str
    change_note: str
    created_at: str
    published_at: str | None = None


class MarketPackComponentInput(BaseModel):
    key: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=2, max_length=80)
    base_score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)


class MarketPackDraftRequest(BaseModel):
    name: str = Field(min_length=4, max_length=160)
    country: str = Field(min_length=2, max_length=80)
    sector: str = Field(min_length=2, max_length=80)
    change_note: str = Field(min_length=8, max_length=1000)
    components: list[MarketPackComponentInput] = Field(min_length=1, max_length=10)


class MarketPackDetail(MarketPackSummary):
    components: list[MarketPackComponentInput]


class MarketPackExport(BaseModel):
    format_version: Literal[1] = 1
    exported_at: str
    source: MarketPackSummary
    template: MarketPackDraftRequest


class MarketPackImportRequest(BaseModel):
    pack_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    template: MarketPackDraftRequest


class MarketPackPreview(ScenarioResult):
    pack_id: str
    version: int
    status: Literal["draft", "published", "archived"]
    mode: Literal["sandbox"] = "sandbox"


class CountryProfile(BaseModel):
    id: Literal["de", "es", "fr", "ae", "sa"]
    name: str
    display_name: str
    market_label: str
    market_pack_id: str
    latitude: float
    longitude: float
    timezone: str
    news_query: str


class CountryWorkspace(BaseModel):
    profile: CountryProfile
    market_pack: MarketPackDetail
    overview: MarketOverview
    sources: list[PublicDataSource]
    news: list[NewsItem]
    features: FactorSnapshot | None = None
    impact_matrix: ImpactMatrix | None = None
    evidence_timeline: list[EvidenceItem] = Field(default_factory=list)


class CountryRefreshResult(BaseModel):
    profile_id: str
    data: DataRefreshResult
    news: NewsRefreshResult


class ResearchReport(BaseModel):
    id: str
    profile_id: str
    market_pack_id: str
    market_pack_version: int
    score: float
    recommendation: str
    markdown: str
    created_at: str
    available_formats: list[Literal["docx", "pdf"]] = ["docx", "pdf"]


class ReportEmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    formats: list[Literal["docx", "pdf"]] = Field(min_length=1, max_length=2)

    @field_validator("email")
    @classmethod
    def valid_email_shape(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("A valid email address is required")
        return cleaned


class ReportEmailResult(BaseModel):
    mode: Literal["preview", "sent", "failed"]
    subject: str
    message: str
    attachments: list[str]


class RawObservation(BaseModel):
    profile_id: str
    source_id: str
    metric_key: str
    observed_at: str
    value: float | None = None
    unit: str
    status: Literal["observed", "missing", "degraded"] = "observed"
    payload_json: str = "{}"
    fetched_at: str | None = None


class EvidenceItemInput(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    source: str = Field(min_length=2, max_length=200)
    url: str | None = Field(default=None, max_length=1000)
    summary: str = ""
    excerpt: str = ""
    published_at: str | None = None
    language: str = "unknown"
    category: str = "market"
    event_type: str = "monitor"
    impact_direction: Literal["positive", "negative", "mixed", "unknown"] = "unknown"
    impact_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    extraction_mode: Literal["rules", "ollama", "manual"] = "rules"


class EvidenceItem(EvidenceItemInput):
    id: str
    profile_id: str
    acknowledged: bool = False
    created_at: str


class ExtractedEvent(BaseModel):
    event_type: Literal["policy", "auction", "grid", "demand", "trade", "finance", "monitor"]
    impact_direction: Literal["positive", "negative", "mixed", "unknown"]
    impact_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    summary: str
    extraction_mode: Literal["rules", "ollama"] = "rules"


class FactorItem(BaseModel):
    key: str
    label: str
    score: float
    base_score: float
    contribution: float
    status: Literal["observed", "derived", "assumption", "insufficient"]
    coverage_ratio: float
    missing_ratio: float
    freshness_label: str
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str


class FactorSnapshot(BaseModel):
    id: str
    profile_id: str
    market_pack_id: str
    market_pack_version: int
    captured_at: str
    items: list[FactorItem]


class ImpactMatrix(BaseModel):
    profile_id: str
    captured_at: str
    items: list[FactorItem]


ProjectStage = Literal["screening", "due_diligence", "review", "admitted", "on_hold", "rejected"]
TaskPriority = Literal["blocker", "high", "normal"]
TaskStatus = Literal["open", "in_progress", "done", "not_applicable"]


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    profile_id: Literal["de", "es", "fr", "ae", "sa"]
    owner: str = Field(default="Development Desk", min_length=2, max_length=80)
    capacity_mw: float | None = Field(default=None, gt=0, le=5000)
    target_cod: str | None = Field(default=None, max_length=10)


class ProjectUpdateRequest(BaseModel):
    stage: ProjectStage | None = None
    owner: str | None = Field(default=None, min_length=2, max_length=80)
    decision_note: str | None = Field(default=None, max_length=2000)


class ProjectOpportunity(ProjectCreateRequest):
    id: str
    stage: ProjectStage = "screening"
    decision_note: str | None = None
    created_at: str
    updated_at: str


class DueDiligenceTaskUpdate(BaseModel):
    status: TaskStatus
    completion_note: str | None = Field(default=None, max_length=2000)


class DueDiligenceTask(BaseModel):
    id: str
    project_id: str
    profile_id: Literal["de", "es", "fr", "ae", "sa"]
    factor_key: str
    title: str
    priority: TaskPriority
    status: TaskStatus
    owner: str
    due_date: str
    evidence_ids: list[str] = Field(default_factory=list)
    assessment_id: str | None = None
    completion_note: str | None = None
    created_at: str
    updated_at: str


class AdmissionAssessment(BaseModel):
    id: str
    project_id: str
    profile_id: Literal["de", "es", "fr", "ae", "sa"]
    factor_snapshot_id: str
    verdict: Literal["ready_for_review", "needs_due_diligence", "not_ready"]
    risk_level: Literal["low", "medium", "high"]
    blockers: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    summary: str
    created_at: str
