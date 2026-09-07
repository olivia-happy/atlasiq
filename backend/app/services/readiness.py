from __future__ import annotations

from ..schemas import DecisionReadiness, DecisionReadinessCheck
from .research import list_research_runs
from .sources import list_public_sources


def get_decision_readiness() -> DecisionReadiness:
    latest_run = next(iter(list_research_runs(limit=1)), None)
    evidence_count = len(latest_run.evidence_ids) if latest_run else 0

    if evidence_count >= 2:
        evidence = DecisionReadinessCheck(
            key="evidence",
            label="证据覆盖",
            status="pass",
            detail=f"最近一次研究绑定了 {evidence_count} 条可追溯证据。",
            score=50,
            max_score=50,
        )
    elif evidence_count == 1:
        evidence = DecisionReadinessCheck(
            key="evidence",
            label="证据覆盖",
            status="caution",
            detail="最近一次研究只绑定了 1 条证据，建议补充交叉验证。",
            score=25,
            max_score=50,
        )
    else:
        evidence = DecisionReadinessCheck(
            key="evidence",
            label="证据覆盖",
            status="missing",
            detail="尚无带证据编号的研究运行记录。",
            score=0,
            max_score=50,
        )

    sources = list_public_sources()
    if sources and all(source.status == "live" for source in sources):
        source_freshness = DecisionReadinessCheck(
            key="source_freshness",
            label="数据新鲜度",
            status="pass",
            detail="全部公开数据源均已完成最近一次刷新。",
            score=30,
            max_score=30,
        )
    elif sources and all(source.status != "degraded" for source in sources):
        source_freshness = DecisionReadinessCheck(
            key="source_freshness",
            label="数据新鲜度",
            status="caution",
            detail="数据源已配置，但仍建议在正式结论前刷新公开快照。",
            score=15,
            max_score=30,
        )
    else:
        source_freshness = DecisionReadinessCheck(
            key="source_freshness",
            label="数据新鲜度",
            status="missing",
            detail="至少一个公开数据源处于降级状态，请先刷新并复核。",
            score=0,
            max_score=30,
        )

    if latest_run:
        runtime_detail = (
            "最近一次研究由本地 Ollama 流式生成，运行参数与证据已留存。"
            if latest_run.mode == "ollama"
            else "最近一次研究走受控降级路径，仍基于服务端限定证据并已留存运行记录。"
        )
        audit_trace = DecisionReadinessCheck(
            key="audit_trace",
            label="运行审计",
            status="pass",
            detail=runtime_detail,
            score=20,
            max_score=20,
        )
    else:
        audit_trace = DecisionReadinessCheck(
            key="audit_trace",
            label="运行审计",
            status="missing",
            detail="尚未形成可回放的研究运行记录。",
            score=0,
            max_score=20,
        )

    checks = [evidence, source_freshness, audit_trace]
    score = sum(check.score for check in checks)
    if evidence.status == "pass" and source_freshness.status != "missing" and audit_trace.status == "pass":
        status = "ready"
        next_action = "信息已满足人工决策前的最小复核条件；保存决策卡前请确认业务判断。"
    elif score >= 40:
        status = "caution"
        next_action = "可继续形成工作假设，但请先补齐黄色检查项再做正式决策。"
    else:
        status = "not_ready"
        next_action = "先运行一次带证据的研究，再进入人工决策与复盘流程。"
    return DecisionReadiness(score=score, status=status, next_action=next_action, checks=checks)
