from __future__ import annotations

from uuid import uuid4

from ..data import iso_now
from ..schemas import FactorItem, FactorSnapshot, ImpactMatrix
from .countries import get_country_profile
from .feature_store import latest_factor_snapshot, list_evidence, list_observations, save_factor_snapshot, save_observations
from .market_packs import active_component_configs, active_pack_version
from .public_data import fetch_pvgis, fetch_world_bank
from .sources import now_iso, save_source_audits, stored_source_audits


FACTOR_DEFINITIONS = (
    ("market_growth", "市场增长", "growth", 68.0),
    ("power_demand", "电力需求", "demand", 66.0),
    ("solar_resource", "光照与发电潜力", "resource", 70.0),
    ("project_economics", "项目经济性", None, 65.0),
    ("grid_absorption", "并网与消纳", None, 62.0),
    ("policy_auction", "政策与招标", "policy", 64.0),
    ("macro_finance", "宏观与融资", None, 64.0),
    ("supply_trade", "供应链与贸易", None, 60.0),
)


def latest_values(profile_id: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for observation in list_observations(profile_id):
        result.setdefault(observation.metric_key, observation)
    return result


def build_factor_snapshot(profile_id: str) -> FactorSnapshot:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    component_by_key = {item["key"]: item for item in active_component_configs(profile.market_pack_id)}
    values = latest_values(profile_id)
    evidence = list_evidence(profile_id)
    items: list[FactorItem] = []
    for key, label, legacy_key, default_base in FACTOR_DEFINITIONS:
        base = float(component_by_key.get(legacy_key, {}).get("base_score", default_base))
        metric_keys = {
            "solar_resource": ["annual_irradiation", "pv_yield"],
            "macro_finance": ["gdp_growth", "fdi_percent_gdp"],
            "power_demand": ["electricity_access", "renewable_electricity_share"],
        }.get(key, [])
        available = [values[item] for item in metric_keys if item in values and getattr(values[item], "value", None) is not None]
        source_ids = sorted({item.source_id for item in available})
        matching_evidence = [item.id for item in evidence if key in item.impact_factors]
        coverage = round(len(available) / len(metric_keys), 2) if metric_keys else 0.0
        if coverage > 0:
            status = "observed"
            adjustment = 0.0
            if key == "solar_resource":
                yield_value = next((item.value for item in available if item.metric_key == "pv_yield"), None)
                adjustment = max(-8, min(8, ((yield_value or 1400) - 1400) / 50))
            elif key == "macro_finance":
                growth = next((item.value for item in available if item.metric_key == "gdp_growth"), 0) or 0
                adjustment = max(-6, min(6, growth - 2))
            score = round(max(0, min(100, base + adjustment)), 1)
            explanation = f"基于 {', '.join(source_ids)} 的 {len(available)}/{len(metric_keys)} 个可用观测计算；未提供的指标保持缺失。"
        elif matching_evidence:
            status = "assumption"
            score = base
            explanation = "存在文本证据，但尚未经人工确认，因此不直接调整评分。"
        else:
            status = "insufficient"
            score = base
            explanation = "当前没有足够的结构化观测或已确认事件；显示 Market Pack 基线而非实时测量。"
        items.append(FactorItem(
            key=key, label=label, score=score, base_score=base, contribution=round(score - base, 1),
            status=status, coverage_ratio=coverage, missing_ratio=round(1 - coverage, 2),
            freshness_label="本次刷新" if available else "尚未观测", source_ids=source_ids,
            evidence_ids=matching_evidence, explanation=explanation,
        ))
    snapshot = FactorSnapshot(
        id=f"FS-{uuid4().hex[:16]}", profile_id=profile_id, market_pack_id=profile.market_pack_id,
        market_pack_version=active_pack_version(profile.market_pack_id), captured_at=iso_now(), items=items,
    )
    return save_factor_snapshot(snapshot)


def get_impact_matrix(profile_id: str) -> ImpactMatrix:
    snapshot = latest_factor_snapshot(profile_id) or build_factor_snapshot(profile_id)
    return ImpactMatrix(profile_id=profile_id, captured_at=snapshot.captured_at, items=snapshot.items)


def refresh_feature_sources(profile_id: str) -> FactorSnapshot:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    checked_at = now_iso()
    existing = stored_source_audits(profile_id)
    observations = []
    audits: dict[str, dict[str, str | None]] = {}
    for source_id, adapter, label in (
        ("pvgis", fetch_pvgis, "PV potential observation"),
        ("world-bank", fetch_world_bank, "Macro and energy indicator"),
    ):
        try:
            source_observations = adapter(profile)
            observations.extend(source_observations)
            observation_period = max((item.observed_at for item in source_observations), default="latest")
            audits[source_id] = {
                "status": "live",
                "last_checked_at": checked_at,
                "last_success_at": checked_at,
                "observation_label": f"{label}: {observation_period}",
            }
        except Exception:
            prior = existing.get(source_id)
            audits[source_id] = {
                "status": "degraded",
                "last_checked_at": checked_at,
                "last_success_at": prior.last_success_at if prior is not None else None,
                "observation_label": prior.observation_label if prior is not None else f"{label} unavailable; last success retained",
            }
    save_source_audits(profile_id, audits)
    if observations:
        save_observations(profile_id, observations)
    return build_factor_snapshot(profile_id)
