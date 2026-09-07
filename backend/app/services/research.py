from __future__ import annotations

import asyncio
import json
import math
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import httpx
from sqlalchemy import select

from ..db import ResearchOutputRecord, ResearchRunRecord, session_scope
from ..schemas import Evidence, ResearchObservability, ResearchRequest, ResearchRun, ResearchRuntime
from .market import get_overview, run_scenario
from .countries import get_country_profile
from .news import list_news
from .feature_store import list_evidence
from .sources import list_public_sources


def sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_research_run(
    *,
    question: str,
    profile_id: str,
    score: float,
    recommendation: str,
    mode: str,
    model: str | None,
    latency_ms: int,
    evidence_ids: list[str],
    answer: str,
) -> ResearchRun:
    run = ResearchRun(
        id=uuid4().hex,
        question=question,
        profile_id=profile_id,
        score=score,
        recommendation=recommendation,
        mode=mode,
        model=model,
        latency_ms=latency_ms,
        evidence_ids=evidence_ids,
        created_at=now_iso(),
        answer=answer,
    )
    with session_scope() as session:
        session.add(
            ResearchRunRecord(
                id=run.id,
                question=run.question,
                profile_id=run.profile_id,
                score=run.score,
                recommendation=run.recommendation,
                mode=run.mode,
                model=run.model,
                latency_ms=run.latency_ms,
                evidence_json=json.dumps(run.evidence_ids),
                created_at=run.created_at,
            )
        )
        session.add(ResearchOutputRecord(research_run_id=run.id, answer=answer))
    return run


def list_research_runs(limit: int = 8) -> list[ResearchRun]:
    with session_scope() as session:
        records = session.scalars(
            select(ResearchRunRecord).order_by(ResearchRunRecord.created_at.desc()).limit(limit)
        ).all()
        outputs = {
            output.research_run_id: output.answer
            for output in session.scalars(
                select(ResearchOutputRecord).where(ResearchOutputRecord.research_run_id.in_([record.id for record in records]))
            ).all()
        } if records else {}
    return [
        ResearchRun(
            id=record.id,
            question=record.question,
            profile_id=record.profile_id,
            score=record.score,
            recommendation=record.recommendation,
            mode=record.mode,
            model=record.model,
            latency_ms=record.latency_ms,
            evidence_ids=json.loads(record.evidence_json),
            created_at=record.created_at,
            answer=outputs.get(record.id),
        )
        for record in records
    ]


def summarize_research_runs(runs: list[ResearchRun]) -> ResearchObservability:
    if not runs:
        return ResearchObservability(
            sample_size=0,
            p50_latency_ms=None,
            p95_latency_ms=None,
            fallback_rate=None,
            evidence_coverage=None,
            last_run_at=None,
        )
    latencies = sorted(run.latency_ms for run in runs)

    def nearest_rank(percentile: float) -> int:
        return latencies[max(0, math.ceil(len(latencies) * percentile) - 1)]

    sample_size = len(runs)
    return ResearchObservability(
        sample_size=sample_size,
        p50_latency_ms=nearest_rank(0.5),
        p95_latency_ms=nearest_rank(0.95),
        fallback_rate=round(sum(run.mode == "fallback" for run in runs) / sample_size, 3),
        evidence_coverage=round(sum(bool(run.evidence_ids) for run in runs) / sample_size, 3),
        last_run_at=max(run.created_at for run in runs),
    )


def get_research_observability() -> ResearchObservability:
    return summarize_research_runs(list_research_runs(limit=200))


def evidence_for_profile(profile_id: str, question: str) -> list[Evidence]:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    prefix = profile.id.upper()
    sources = list_public_sources(profile_id)
    evidence = [
        Evidence(
            id=f"{prefix}-PACK",
            title=f"{profile.name} Market Pack configuration",
            source="AtlasIQ local configuration",
            excerpt=f"Active market pack: {profile.market_pack_id}; transparent scoring weights are reviewable in the workspace.",
            metric="market_pack",
        )
    ]
    for source in sources:
        evidence.append(
            Evidence(
                id=f"{prefix}-{source.id.upper()}",
                title=f"{profile.name} {source.name} freshness",
                source=source.name,
                excerpt=f"Status: {source.status}; observation: {source.observation_label}.",
                metric=source.id,
            )
        )
    for item in list_news(profile_id)[:1]:
        evidence.append(
            Evidence(
                id=f"{prefix}-NEWS",
                title=item.title,
                source=item.source,
                excerpt=item.why,
                metric="news_signal",
            )
        )
    for item in list_evidence(profile_id, limit=3):
        confirmation = "confirmed" if item.acknowledged else "unconfirmed"
        evidence.append(
            Evidence(
                id=f"{prefix}-{item.id}",
                title=item.title,
                source=item.source,
                excerpt=(
                    f"{item.summary or item.excerpt} "
                    f"Event: {item.event_type}; direction: {item.impact_direction}; "
                    f"factors: {', '.join(item.impact_factors) or 'monitoring only'}; "
                    f"status: {confirmation}."
                ),
                metric=f"evidence:{item.event_type}",
            )
        )
    lowered = question.lower()
    if "政策" in question or "policy" in lowered or "补贴" in question:
        return [item for item in evidence if item.metric in {"market_pack", "news_signal", "evidence:policy", "evidence:auction"}] or evidence[:1]
    return evidence


def fallback_answer(profile_name: str, question: str, score: float, recommendation: str, evidence: list[Evidence]) -> str:
    evidence_ids = "、".join(f"[{item.id}]" for item in evidence)
    return (
        f"基于当前已入库的 {profile_name} 新能源市场工作台，机会评分为 {score:.1f}/100，建议为“{recommendation}”。"
        f"市场增长和需求指标支撑继续研究，但政策确定性与并网执行风险仍是需要核验的前提。"
        f"针对你的问题“{question}”，建议先把政策支持强度和电网风险作为情景变量复核，再形成进入节奏。证据：{evidence_ids}。"
    )


async def ollama_tokens(prompt: str) -> AsyncIterator[str]:
    base_url = os.getenv("OLLAMA_BASE_URL")
    model = os.getenv("OLLAMA_MODEL")
    if not base_url or not model:
        return
    payload = {"model": model, "prompt": prompt, "stream": True, "options": {"temperature": 0.2}}
    async with httpx.AsyncClient(timeout=25) as client:
        async with client.stream("POST", f"{base_url.rstrip('/')}/api/generate", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                item = json.loads(line)
                token = item.get("response", "")
                if token:
                    yield token


async def stream_research(request: ResearchRequest) -> AsyncIterator[str]:
    started_at = perf_counter()
    yield sse("status", {"label": "正在检索市场指标与证据"})
    await asyncio.sleep(0.1)
    profile = get_country_profile(request.profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    overview = get_overview(request.profile_id)
    if request.scenario:
        scenario = run_scenario(request.scenario, request.profile_id)
        score = scenario.score
        recommendation = scenario.recommendation
    else:
        score = overview.score
        recommendation = overview.recommendation
    evidence = evidence_for_profile(request.profile_id, request.question)
    yield sse("status", {"label": "正在执行受控趋势与情景分析"})
    await asyncio.sleep(0.1)
    context = "\n".join(f"[{item.id}] {item.title}: {item.excerpt}" for item in evidence)
    prompt = (
        "你是 AtlasIQ 的研究助理。只能依据以下证据与评分回答；不要提供投资建议，不要虚构来源。"
        f"\n国家: {profile.name}，评分: {score}，建议标签: {recommendation}\n证据:\n{context}\n问题: {request.question}\n"
        "请用中文输出简洁研究结论，并在结尾保留证据编号。"
    )
    yield sse("status", {"label": "正在生成带证据的研究简报"})
    model_streamed = False
    answer_parts: list[str] = []
    try:
        async for token in ollama_tokens(prompt):
            model_streamed = True
            answer_parts.append(token)
            yield sse("token", {"text": token})
    except (httpx.HTTPError, json.JSONDecodeError, OSError):
        model_streamed = False
    if not model_streamed:
        answer = fallback_answer(profile.name, request.question, score, recommendation, evidence)
        for word in answer.split("，"):
            answer_parts.append(word + "，")
            yield sse("token", {"text": word + "，"})
            await asyncio.sleep(0.03)
    yield sse("citations", {"items": [item.model_dump() for item in evidence]})
    mode = "ollama" if model_streamed else "fallback"
    run = record_research_run(
        question=request.question,
        profile_id=request.profile_id,
        score=score,
        recommendation=recommendation,
        mode=mode,
        model=os.getenv("OLLAMA_MODEL") if mode == "ollama" else None,
        latency_ms=round((perf_counter() - started_at) * 1000),
        evidence_ids=[item.id for item in evidence],
        answer="".join(answer_parts).strip(),
    )
    runtime = ResearchRuntime(**run.model_dump(exclude={"question", "score", "recommendation"}))
    yield sse("done", {"score": score, "recommendation": recommendation, "runtime": runtime.model_dump()})
