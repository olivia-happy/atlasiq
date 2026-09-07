from __future__ import annotations

import json
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from ..data import iso_now
from ..db import AdmissionAssessmentRecord, DueDiligenceTaskRecord, ProjectRecord, session_scope
from ..schemas import AdmissionAssessment, DueDiligenceTask, DueDiligenceTaskUpdate, ProjectCreateRequest, ProjectOpportunity, ProjectUpdateRequest
from .countries import get_country_profile
from .factors import build_factor_snapshot
from .feature_store import list_evidence


def to_project(record: ProjectRecord) -> ProjectOpportunity:
    return ProjectOpportunity(
        id=record.id,
        name=record.name,
        profile_id=record.profile_id,
        owner=record.owner,
        capacity_mw=record.capacity_mw,
        target_cod=record.target_cod,
        stage=record.stage,
        decision_note=record.decision_note,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def create_project(request: ProjectCreateRequest) -> ProjectOpportunity:
    if get_country_profile(request.profile_id) is None:
        raise ValueError("Country profile not found")
    now = iso_now()
    with session_scope() as session:
        record = ProjectRecord(
            id=f"PRJ-{uuid4().hex[:12]}",
            name=request.name,
            profile_id=request.profile_id,
            stage="screening",
            owner=request.owner,
            capacity_mw=request.capacity_mw,
            target_cod=request.target_cod,
            decision_note=None,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.flush()
        return to_project(record)


def list_projects(profile_id: str | None = None) -> list[ProjectOpportunity]:
    with session_scope() as session:
        query = select(ProjectRecord).order_by(ProjectRecord.updated_at.desc())
        if profile_id is not None:
            query = query.where(ProjectRecord.profile_id == profile_id)
        records = session.scalars(query).all()
    return [to_project(record) for record in records]


def clear_project_state() -> None:
    with session_scope() as session:
        session.execute(delete(DueDiligenceTaskRecord))
        session.execute(delete(AdmissionAssessmentRecord))
        session.execute(delete(ProjectRecord))


def get_project(project_id: str) -> ProjectOpportunity | None:
    with session_scope() as session:
        record = session.get(ProjectRecord, project_id)
        return to_project(record) if record is not None else None


def to_task(record: DueDiligenceTaskRecord) -> DueDiligenceTask:
    return DueDiligenceTask(
        id=record.id,
        project_id=record.project_id,
        profile_id=record.profile_id,
        factor_key=record.factor_key,
        title=record.title,
        priority=record.priority,
        status=record.status,
        owner=record.owner,
        due_date=record.due_date,
        evidence_ids=json.loads(record.evidence_ids_json),
        assessment_id=record.assessment_id,
        completion_note=record.completion_note,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def list_project_tasks(project_id: str) -> list[DueDiligenceTask]:
    with session_scope() as session:
        records = session.scalars(
            select(DueDiligenceTaskRecord)
            .where(DueDiligenceTaskRecord.project_id == project_id)
            .order_by(DueDiligenceTaskRecord.priority, DueDiligenceTaskRecord.created_at)
        ).all()
    return [to_task(record) for record in records]


def update_project_task(
    project_id: str,
    task_id: str,
    status: str,
    completion_note: str | None = None,
) -> DueDiligenceTask | None:
    with session_scope() as session:
        record = session.get(DueDiligenceTaskRecord, task_id)
        if record is None or record.project_id != project_id:
            return None
        record.status = status
        record.completion_note = completion_note
        record.updated_at = iso_now()
        session.flush()
        return to_task(record)


def update_project(project_id: str, request: ProjectUpdateRequest) -> ProjectOpportunity | None:
    with session_scope() as session:
        record = session.get(ProjectRecord, project_id)
        if record is None:
            return None
        if request.stage in {"review", "admitted"}:
            open_blockers = session.scalars(
                select(DueDiligenceTaskRecord).where(
                    DueDiligenceTaskRecord.project_id == project_id,
                    DueDiligenceTaskRecord.priority == "blocker",
                    DueDiligenceTaskRecord.status.in_(["open", "in_progress"]),
                )
            ).all()
            if open_blockers:
                raise ValueError("Open blocker tasks must be resolved before review or admission")
        if request.stage == "admitted" and not (request.decision_note or record.decision_note):
            raise ValueError("An admitted project requires an explicit human decision note")
        if request.stage is not None:
            record.stage = request.stage
        if request.owner is not None:
            record.owner = request.owner
        if request.decision_note is not None:
            record.decision_note = request.decision_note
        record.updated_at = iso_now()
        session.flush()
        return to_project(record)


def to_assessment(record: AdmissionAssessmentRecord) -> AdmissionAssessment:
    return AdmissionAssessment(
        id=record.id,
        project_id=record.project_id,
        profile_id=record.profile_id,
        factor_snapshot_id=record.factor_snapshot_id,
        verdict=record.verdict,
        risk_level=record.risk_level,
        blockers=json.loads(record.blockers_json),
        task_ids=json.loads(record.task_ids_json),
        summary=record.summary,
        created_at=record.created_at,
    )


FACTOR_TASKS: dict[str, tuple[str, str, str]] = {
    "grid_absorption": ("核验并网接入与限电风险", "blocker", "Obtain grid connection queue, capacity and curtailment evidence."),
    "policy_auction": ("核验政策、招标与许可路径", "blocker", "Validate current support scheme, auction eligibility and permitting route."),
    "project_economics": ("补齐项目经济性假设", "blocker", "Build site-level CAPEX, revenue, PPA and return sensitivity assumptions."),
    "supply_trade": ("核验供应链与贸易约束", "normal", "Check module sourcing, trade restrictions and delivery exposure."),
    "macro_finance": ("补齐融资与宏观数据", "high", "Validate financing conditions and current macro assumptions."),
    "power_demand": ("补齐电力需求与消纳数据", "high", "Validate demand, offtake and grid absorption assumptions."),
    "solar_resource": ("补齐资源评估", "high", "Validate irradiation and preliminary yield assumptions for the target site."),
}


def assessment_requirements(snapshot) -> list[tuple[str, str, str, list[str]]]:
    required: list[tuple[str, str, str, list[str]]] = []
    by_key = {item.key: item for item in snapshot.items}
    for key in ("grid_absorption", "policy_auction", "project_economics"):
        item = by_key[key]
        if item.status in {"insufficient", "assumption"}:
            title, priority, _ = FACTOR_TASKS[key]
            required.append((key, title, priority, item.evidence_ids))
    for key in ("solar_resource", "macro_finance", "power_demand", "supply_trade"):
        item = by_key[key]
        if item.status == "insufficient":
            title, priority, _ = FACTOR_TASKS[key]
            required.append((key, title, priority, item.evidence_ids))
    return required


def ensure_open_task(
    *, session, project: ProjectRecord, factor_key: str, title: str, priority: str, evidence_ids: list[str], assessment_id: str,
) -> DueDiligenceTaskRecord:
    now = iso_now()
    existing = next(
        iter(
            session.scalars(
                select(DueDiligenceTaskRecord).where(
                    DueDiligenceTaskRecord.project_id == project.id,
                    DueDiligenceTaskRecord.factor_key == factor_key,
                    DueDiligenceTaskRecord.status.in_(["open", "in_progress"]),
                )
            ).all()
        ),
        None,
    )
    if existing is not None:
        existing.evidence_ids_json = json.dumps(sorted(set(json.loads(existing.evidence_ids_json) + evidence_ids)))
        existing.assessment_id = assessment_id
        existing.updated_at = now
        return existing
    record = DueDiligenceTaskRecord(
        id=f"DD-{uuid4().hex[:12]}",
        project_id=project.id,
        profile_id=project.profile_id,
        factor_key=factor_key,
        title=title,
        priority=priority,
        status="open",
        owner=project.owner,
        due_date=(date.today() + timedelta(days=7 if priority == "blocker" else 14)).isoformat(),
        evidence_ids_json=json.dumps(evidence_ids),
        assessment_id=assessment_id,
        completion_note=None,
        created_at=now,
        updated_at=now,
    )
    session.add(record)
    session.flush()
    return record


def assess_project(project_id: str) -> AdmissionAssessment:
    with session_scope() as session:
        project = session.get(ProjectRecord, project_id)
        if project is None:
            raise ValueError("Project not found")
        snapshot = build_factor_snapshot(project.profile_id)
        assessment_id = f"ASM-{uuid4().hex[:12]}"
        requirements = assessment_requirements(snapshot)
        task_records = [
            ensure_open_task(
                session=session,
                project=project,
                factor_key=key,
                title=title,
                priority=priority,
                evidence_ids=evidence_ids,
                assessment_id=assessment_id,
            )
            for key, title, priority, evidence_ids in requirements
        ]
        blockers = [title for _, title, priority, _ in requirements if priority == "blocker"]
        if blockers:
            verdict, risk_level = "not_ready", "high"
        elif requirements:
            verdict, risk_level = "needs_due_diligence", "medium"
        else:
            verdict, risk_level = "ready_for_review", "low"
        summary = (
            "Critical project-entry assumptions require due diligence before a human review."
            if blockers else "Evidence coverage is sufficient for human review."
            if not requirements else "Non-blocking due-diligence items remain open before review."
        )
        record = AdmissionAssessmentRecord(
            id=assessment_id,
            project_id=project.id,
            profile_id=project.profile_id,
            factor_snapshot_id=snapshot.id,
            verdict=verdict,
            risk_level=risk_level,
            blockers_json=json.dumps(blockers),
            task_ids_json=json.dumps([task.id for task in task_records]),
            summary=summary,
            created_at=iso_now(),
        )
        session.add(record)
        session.flush()
        return to_assessment(record)


def trigger_project_reassessment(profile_id: str, evidence_id: str) -> int:
    evidence = next((item for item in list_evidence(profile_id) if item.id == evidence_id), None)
    if evidence is None or not evidence.acknowledged or not evidence.impact_factors:
        return 0
    now = iso_now()
    created = 0
    with session_scope() as session:
        projects = session.scalars(
            select(ProjectRecord).where(
                ProjectRecord.profile_id == profile_id,
                ProjectRecord.stage.in_(["screening", "due_diligence", "review", "on_hold"]),
            )
        ).all()
        for project in projects:
            for factor_key in evidence.impact_factors:
                review_key = f"evidence_review:{factor_key}"
                existing = session.scalar(
                    select(DueDiligenceTaskRecord).where(
                        DueDiligenceTaskRecord.project_id == project.id,
                        DueDiligenceTaskRecord.factor_key == review_key,
                        DueDiligenceTaskRecord.status.in_(["open", "in_progress"]),
                    )
                )
                if existing is not None:
                    known_ids = json.loads(existing.evidence_ids_json)
                    if evidence_id not in known_ids:
                        existing.evidence_ids_json = json.dumps(sorted([*known_ids, evidence_id]))
                        existing.updated_at = now
                    continue
                session.add(DueDiligenceTaskRecord(
                    id=f"DD-{uuid4().hex[:12]}",
                    project_id=project.id,
                    profile_id=profile_id,
                    factor_key=review_key,
                    title=f"复核已确认的{factor_key}证据",
                    priority="high",
                    status="open",
                    owner=project.owner,
                    due_date=(date.today() + timedelta(days=3)).isoformat(),
                    evidence_ids_json=json.dumps([evidence_id]),
                    assessment_id=None,
                    completion_note=None,
                    created_at=now,
                    updated_at=now,
                ))
                created += 1
    return created


def latest_project_assessment(project_id: str) -> AdmissionAssessment | None:
    with session_scope() as session:
        record = session.scalar(
            select(AdmissionAssessmentRecord)
            .where(AdmissionAssessmentRecord.project_id == project_id)
            .order_by(AdmissionAssessmentRecord.created_at.desc())
        )
    return to_assessment(record) if record is not None else None


def build_project_briefing(project_id: str) -> str | None:
    project = get_project(project_id)
    if project is None:
        return None
    assessment = latest_project_assessment(project_id)
    tasks = list_project_tasks(project_id)
    task_lines = [
        f"- [{task.status}] {task.priority.upper()} · {task.title} · owner: {task.owner} · due: {task.due_date}"
        for task in tasks
    ] or ["- No due-diligence tasks exist yet. Run an admission assessment first."]
    evidence_ids = sorted({evidence_id for task in tasks for evidence_id in task.evidence_ids})
    evidence_lines = [f"- {evidence_id}" for evidence_id in evidence_ids] or ["- No evidence IDs attached to current tasks."]
    assessment_lines = (
        [
            f"- Assessment ID: {assessment.id}",
            f"- Factor snapshot: {assessment.factor_snapshot_id}",
            f"- Verdict: {assessment.verdict}",
            f"- Risk level: {assessment.risk_level}",
            f"- Blockers: {', '.join(assessment.blockers) or 'none'}",
            f"- Summary: {assessment.summary}",
        ]
        if assessment is not None else ["- No saved assessment. Run the admission assessment before a review meeting."]
    )
    return "\n".join([
        "# AtlasIQ Project Admission Briefing",
        "",
        "## Project",
        f"- Project ID: {project.id}",
        f"- Name: {project.name}",
        f"- Country profile: {project.profile_id}",
        f"- Stage: {project.stage}",
        f"- Owner: {project.owner}",
        f"- Capacity MW: {project.capacity_mw if project.capacity_mw is not None else 'not specified'}",
        f"- Target COD: {project.target_cod or 'not specified'}",
        f"- Human decision note: {project.decision_note or 'not recorded'}",
        "",
        "## Admission assessment",
        *assessment_lines,
        "",
        "## Due-diligence tasks",
        *task_lines,
        "",
        "## Evidence IDs",
        *evidence_lines,
        "",
        "## Decision boundary",
        "This briefing supports a human project-entry review. It does not approve investment, permitting, grid connection or commercial commitments automatically.",
    ])
