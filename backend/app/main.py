from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from .schemas import (
    AcknowledgeResult,
    EmailPreviewRequest,
    EmailPreviewResult,
    Evidence,
    DataRefreshResult,
    DemoSeedResult,
    DecisionReadiness,
    DecisionCard,
    DecisionCardRequest,
    DecisionReview,
    DecisionReviewQueue,
    DecisionReviewRequest,
    DecisionReviewTrigger,
    MarketOverview,
    MarketPackDetail,
    MarketPackSummary,
    MarketPackDraftRequest,
    MarketPackExport,
    MarketPackImportRequest,
    MarketPackPreview,
    NewsItem,
    NewsPollingStatus,
    NewsRefreshResult,
    NotificationDelivery,
    PublicDataSource,
    ResearchObservability,
    ResearchRequest,
    ResearchRun,
    ScenarioRequest,
    ScenarioResult,
    SensitivityResult,
    SimulationResult,
    Subscription,
    SubscriptionRequest,
    CountryProfile,
    CountryRefreshResult,
    EvidenceItem,
    FactorSnapshot,
    ImpactMatrix,
    CountryWorkspace,
    ResearchReport,
    ReportEmailRequest,
    ReportEmailResult,
    ProjectOpportunity,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    AdmissionAssessment,
    DueDiligenceTask,
    DueDiligenceTaskUpdate,
)
from .services.countries import get_country_profile, get_country_workspace, list_country_profiles
from .services.reports import create_research_report, get_research_report, read_report_file
from .services.factors import build_factor_snapshot, get_impact_matrix, refresh_feature_sources
from .services.feature_store import acknowledge_evidence, list_evidence
from .services.market import get_overview, run_configured_scenario, run_scenario, sensitivity_analysis, simulate_uncertainty
from .services.market_packs import create_draft, export_market_pack_version, get_market_pack_version, import_market_pack, list_market_packs, publish_draft
from .services.news import acknowledge, list_news, refresh_live_news
from .services.polling import get_news_polling_status, news_poll_interval_seconds
from .services.notifications import create_subscription, list_deliveries, list_subscriptions, preview_report_email, send_email_or_preview, send_report_email
from .services.research import get_research_observability, list_research_runs, stream_research
from .services.readiness import get_decision_readiness
from .services.sources import list_public_sources, refresh_public_snapshots
from .db import init_db
from .services.decisions import build_decision_briefing, create_decision_card, create_decision_review, get_review_queue, get_review_triggers, list_decision_cards, list_decision_reviews, list_evidence_snapshots, seed_demo_workspace
from .services.projects import assess_project, build_project_briefing, create_project, get_project, list_project_tasks, list_projects, trigger_project_reassessment, update_project, update_project_task

async def news_poll_loop(interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await asyncio.to_thread(refresh_live_news)
        except Exception:
            continue


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    interval_seconds = news_poll_interval_seconds()
    task = asyncio.create_task(news_poll_loop(interval_seconds)) if interval_seconds > 0 else None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="AtlasIQ API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/countries", response_model=list[CountryProfile])
def countries() -> list[CountryProfile]:
    return list_country_profiles()


@app.get("/api/countries/{profile_id}/workspace", response_model=CountryWorkspace)
def country_workspace(profile_id: str) -> CountryWorkspace:
    workspace = get_country_workspace(profile_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Country profile not found")
    return workspace


@app.post("/api/countries/{profile_id}/refresh", response_model=CountryRefreshResult)
def refresh_country(profile_id: str) -> CountryRefreshResult:
    if get_country_workspace(profile_id) is None:
        raise HTTPException(status_code=404, detail="Country profile not found")
    return CountryRefreshResult(
        profile_id=profile_id,
        data=refresh_public_snapshots(profile_id),
        news=refresh_live_news(profile_id, dispatch_notifications=False),
    )


@app.get("/api/countries/{profile_id}/features", response_model=FactorSnapshot)
def country_features(profile_id: str) -> FactorSnapshot:
    try:
        return build_factor_snapshot(profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/countries/{profile_id}/features/refresh", response_model=FactorSnapshot)
def refresh_country_features(profile_id: str) -> FactorSnapshot:
    try:
        return refresh_feature_sources(profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/countries/{profile_id}/impact-matrix", response_model=ImpactMatrix)
def country_impact_matrix(profile_id: str) -> ImpactMatrix:
    try:
        return get_impact_matrix(profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/countries/{profile_id}/evidence", response_model=list[EvidenceItem])
def country_evidence(profile_id: str) -> list[EvidenceItem]:
    if get_country_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="Country profile not found")
    return list_evidence(profile_id)


@app.get("/api/countries/{profile_id}/evidence/timeline", response_model=list[EvidenceItem])
def country_evidence_timeline(profile_id: str) -> list[EvidenceItem]:
    if get_country_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="Country profile not found")
    return sorted(
        list_evidence(profile_id),
        key=lambda item: item.published_at or item.created_at,
        reverse=True,
    )


@app.post("/api/countries/{profile_id}/evidence/{evidence_id}/acknowledge", response_model=EvidenceItem)
def confirm_country_evidence(profile_id: str, evidence_id: str) -> EvidenceItem:
    if get_country_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="Country profile not found")
    evidence = acknowledge_evidence(profile_id, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence item not found")
    trigger_project_reassessment(profile_id, evidence.id)
    return evidence


@app.post("/api/countries/{profile_id}/scenarios", response_model=ScenarioResult)
def country_scenario(profile_id: str, request: ScenarioRequest) -> ScenarioResult:
    try:
        return run_scenario(request, profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/countries/{profile_id}/simulations", response_model=SimulationResult)
def country_simulation(profile_id: str, request: ScenarioRequest) -> SimulationResult:
    try:
        return simulate_uncertainty(request, profile_id=profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/countries/{profile_id}/sensitivity", response_model=SensitivityResult)
def country_sensitivity(profile_id: str, request: ScenarioRequest) -> SensitivityResult:
    try:
        return sensitivity_analysis(request, profile_id=profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/countries/{profile_id}/research-report", response_model=ResearchReport)
def create_country_report(profile_id: str, request: ScenarioRequest) -> ResearchReport:
    try:
        return create_research_report(profile_id, request)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/reports/{report_id}", response_model=ResearchReport)
def report(report_id: str) -> ResearchReport:
    result = get_research_report(report_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Research report not found")
    return result


@app.get("/api/reports/{report_id}/download")
def download_report(report_id: str, format: str) -> FileResponse:
    file_path = read_report_file(report_id, format)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Research report file not found")
    media_type = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)


@app.post("/api/reports/{report_id}/email-preview", response_model=ReportEmailResult)
def report_email_preview(report_id: str, request: ReportEmailRequest) -> ReportEmailResult:
    try:
        return preview_report_email(report_id, request.email, request.formats)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/reports/{report_id}/send-email", response_model=ReportEmailResult)
def send_report(report_id: str, request: ReportEmailRequest) -> ReportEmailResult:
    try:
        return send_report_email(report_id, request.email, request.formats)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/market/overview", response_model=MarketOverview)
def market_overview() -> MarketOverview:
    return get_overview()


@app.get("/api/market-packs", response_model=list[MarketPackSummary])
def market_packs() -> list[MarketPackSummary]:
    return list_market_packs()


@app.get("/api/market-packs/{pack_id}/versions/{version}", response_model=MarketPackDetail)
def market_pack_version(pack_id: str, version: int) -> MarketPackDetail:
    result = get_market_pack_version(pack_id, version)
    if result is None:
        raise HTTPException(status_code=404, detail="Market pack version not found")
    return result


@app.get("/api/market-packs/{pack_id}/versions/{version}/export", response_model=MarketPackExport)
def export_market_pack(pack_id: str, version: int) -> MarketPackExport:
    result = export_market_pack_version(pack_id, version)
    if result is None:
        raise HTTPException(status_code=404, detail="Market pack version not found")
    return result


@app.post("/api/market-packs/{pack_id}/versions/{version}/preview", response_model=MarketPackPreview)
def preview_market_pack(pack_id: str, version: int, scenario: ScenarioRequest) -> MarketPackPreview:
    detail = get_market_pack_version(pack_id, version)
    if detail is None:
        raise HTTPException(status_code=404, detail="Market pack version not found")
    result = run_configured_scenario([component.model_dump() for component in detail.components], scenario)
    return MarketPackPreview(pack_id=detail.id, version=detail.version, status=detail.status, **result.model_dump())


@app.post("/api/market-packs/imports", response_model=MarketPackSummary, status_code=201)
def import_market_pack_template(request: MarketPackImportRequest) -> MarketPackSummary:
    try:
        return import_market_pack(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/market-packs/{pack_id}/drafts", response_model=MarketPackSummary, status_code=201)
def market_pack_draft(pack_id: str, request: MarketPackDraftRequest) -> MarketPackSummary:
    try:
        return create_draft(pack_id, request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/market-packs/{pack_id}/versions/{version}/publish", response_model=MarketPackSummary)
def publish_market_pack(pack_id: str, version: int) -> MarketPackSummary:
    published = publish_draft(pack_id, version)
    if published is None:
        raise HTTPException(status_code=404, detail="Draft market pack version not found")
    return published


@app.post("/api/market/sensitivity", response_model=SensitivityResult)
def market_sensitivity(scenario: ScenarioRequest) -> SensitivityResult:
    return sensitivity_analysis(scenario)


@app.post("/api/demo/seed", response_model=DemoSeedResult)
def seed_demo() -> DemoSeedResult:
    return seed_demo_workspace()


@app.get("/api/data-sources", response_model=list[PublicDataSource])
def data_sources(profile_id: str = "de") -> list[PublicDataSource]:
    try:
        return list_public_sources(profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/data/refresh", response_model=DataRefreshResult)
def refresh_data() -> DataRefreshResult:
    return refresh_public_snapshots()


@app.get("/api/decision-cards", response_model=list[DecisionCard])
def decision_cards() -> list[DecisionCard]:
    return list_decision_cards()


@app.get("/api/decision-readiness", response_model=DecisionReadiness)
def decision_readiness() -> DecisionReadiness:
    return get_decision_readiness()


@app.get("/api/decision-cards/review-queue", response_model=DecisionReviewQueue)
def decision_review_queue() -> DecisionReviewQueue:
    return get_review_queue()


@app.get("/api/decision-cards/review-triggers", response_model=list[DecisionReviewTrigger])
def decision_review_triggers() -> list[DecisionReviewTrigger]:
    return get_review_triggers()


@app.get("/api/decision-cards/{card_id}/reviews", response_model=list[DecisionReview])
def decision_reviews(card_id: str) -> list[DecisionReview]:
    return list_decision_reviews(card_id)


@app.get("/api/decision-cards/{card_id}/evidence-snapshot", response_model=list[Evidence])
def decision_evidence_snapshot(card_id: str) -> list[Evidence]:
    snapshots = list_evidence_snapshots(card_id)
    if snapshots is None:
        raise HTTPException(status_code=404, detail="Decision card not found")
    return snapshots


@app.post("/api/decision-cards/{card_id}/reviews", response_model=DecisionReview)
def save_decision_review(card_id: str, request: DecisionReviewRequest) -> DecisionReview:
    result = create_decision_review(card_id, request)
    if result is None:
        raise HTTPException(status_code=404, detail="Decision card not found")
    return result


@app.get("/api/decision-cards/{card_id}/briefing", response_class=PlainTextResponse)
def decision_briefing(card_id: str) -> PlainTextResponse:
    briefing = build_decision_briefing(card_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="Decision card not found")
    return PlainTextResponse(
        briefing,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="atlasiq-{card_id}.md"'},
    )


@app.post("/api/decision-cards", response_model=DecisionCard)
def save_decision_card(request: DecisionCardRequest) -> DecisionCard:
    return create_decision_card(request)


@app.post("/api/market/scenarios", response_model=ScenarioResult)
def scenario(request: ScenarioRequest) -> ScenarioResult:
    return run_scenario(request)


@app.get("/api/projects", response_model=list[ProjectOpportunity])
def projects(profile_id: str | None = None) -> list[ProjectOpportunity]:
    if profile_id is not None and get_country_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="Country profile not found")
    return list_projects(profile_id)


@app.post("/api/projects", response_model=ProjectOpportunity, status_code=201)
def create_project_opportunity(request: ProjectCreateRequest) -> ProjectOpportunity:
    try:
        return create_project(request)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/projects/{project_id}", response_model=ProjectOpportunity)
def project(project_id: str) -> ProjectOpportunity:
    result = get_project(project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.patch("/api/projects/{project_id}", response_model=ProjectOpportunity)
def update_project_opportunity(project_id: str, request: ProjectUpdateRequest) -> ProjectOpportunity:
    try:
        result = update_project(project_id, request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@app.post("/api/projects/{project_id}/assessments", response_model=AdmissionAssessment)
def project_assessment(project_id: str) -> AdmissionAssessment:
    try:
        return assess_project(project_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/projects/{project_id}/tasks", response_model=list[DueDiligenceTask])
def project_tasks(project_id: str) -> list[DueDiligenceTask]:
    if get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return list_project_tasks(project_id)


@app.patch("/api/projects/{project_id}/tasks/{task_id}", response_model=DueDiligenceTask)
def update_due_diligence_task(project_id: str, task_id: str, request: DueDiligenceTaskUpdate) -> DueDiligenceTask:
    result = update_project_task(project_id, task_id, request.status, request.completion_note)
    if result is None:
        raise HTTPException(status_code=404, detail="Due-diligence task not found")
    return result


@app.get("/api/projects/{project_id}/briefing", response_class=PlainTextResponse)
def project_briefing(project_id: str) -> PlainTextResponse:
    briefing = build_project_briefing(project_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return PlainTextResponse(
        briefing,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="atlasiq-{project_id}-admission-briefing.md"'},
    )


@app.post("/api/market/simulations", response_model=SimulationResult)
def simulate_market(request: ScenarioRequest) -> SimulationResult:
    return simulate_uncertainty(request)


@app.post("/api/research/ask")
async def ask_research(request: ResearchRequest) -> StreamingResponse:
    if get_country_profile(request.profile_id) is None:
        raise HTTPException(status_code=404, detail="Country profile not found")
    return StreamingResponse(stream_research(request), media_type="text/event-stream")


@app.get("/api/research/runs", response_model=list[ResearchRun])
def research_runs(limit: int = 8) -> list[ResearchRun]:
    return list_research_runs(limit=max(1, min(limit, 30)))


@app.get("/api/research/observability", response_model=ResearchObservability)
def research_observability() -> ResearchObservability:
    return get_research_observability()


@app.get("/api/news", response_model=list[NewsItem])
def news() -> list[NewsItem]:
    return list_news()


@app.post("/api/news/refresh", response_model=NewsRefreshResult)
def refresh_news() -> NewsRefreshResult:
    return refresh_live_news()


@app.get("/api/news/polling-status", response_model=NewsPollingStatus)
def news_polling_status() -> NewsPollingStatus:
    return get_news_polling_status()


@app.get("/api/subscriptions", response_model=list[Subscription])
def subscriptions() -> list[Subscription]:
    return list_subscriptions()


@app.post("/api/subscriptions", response_model=Subscription)
def subscribe(request: SubscriptionRequest) -> Subscription:
    return create_subscription(request)


@app.get("/api/notifications", response_model=list[NotificationDelivery])
def notifications() -> list[NotificationDelivery]:
    return list_deliveries()


@app.post("/api/news/{news_id}/acknowledge", response_model=AcknowledgeResult)
def acknowledge_news(news_id: str) -> AcknowledgeResult:
    result = acknowledge(news_id)
    if result is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return result


@app.post("/api/notifications/test-email", response_model=EmailPreviewResult)
def test_email(request: EmailPreviewRequest) -> EmailPreviewResult:
    return send_email_or_preview(request.email)
