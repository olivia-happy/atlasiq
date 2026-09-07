from __future__ import annotations

from random import Random

from ..data import EVIDENCE, METRICS, iso_now
from ..schemas import MarketOverview, ScenarioRequest, ScenarioResult, ScoreComponent, SensitivityItem, SensitivityResult, SimulationResult
from .cache import get_json, set_json
from .market_packs import active_component_configs, active_pack_version
from .countries import get_country_profile


BASE_COMPONENTS = (
    ("growth", "市场增长", 82.0, 0.35, "公开样例中的装机容量持续增长。"),
    ("resource", "资源条件", 76.0, 0.20, "天气与资源条件保持稳定，需与项目选址数据复核。"),
    ("policy", "政策确定性", 64.0, 0.25, "政策变量存在不确定性，不能用单一新闻替代正式尽调。"),
    ("demand", "需求与电网", 71.0, 0.20, "需求指数高于基线，但并网与执行节奏仍需持续监测。"),
)

SENSITIVITY_DIMENSIONS = (
    ("subsidy_change", "补贴支持", -60, 60),
    ("demand_change", "市场需求", -40, 40),
    ("grid_risk_change", "并网风险", -40, 40),
    ("weather_change", "资源条件", -30, 30),
)


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def recommendation_for(score: float) -> str:
    if score >= 75:
        return "积极研究"
    if score >= 60:
        return "持续观察"
    return "暂缓进入"


def components_for(scenario: ScenarioRequest | None = None, component_configs: list[dict[str, object]] | None = None) -> list[ScoreComponent]:
    scenario = scenario or ScenarioRequest()
    adjustments = {
        "growth": 0.0,
        "resource": scenario.weather_change * 0.15,
        "policy": scenario.subsidy_change * 0.18 - scenario.grid_risk_change * 0.12,
        "demand": scenario.demand_change * 0.45 - scenario.grid_risk_change * 0.28,
    }
    return [
        ScoreComponent(
            key=str(component["key"]),
            label=str(component["label"]),
            score=round(clamp(float(component["base_score"]) + adjustments.get(str(component["key"]), 0.0)), 1),
            weight=float(component["weight"]),
            explanation=str(component.get("explanation", "Configured by the active Market Pack.")),
        )
        for component in component_configs or active_component_configs()
    ]


def weighted_score(components: list[ScoreComponent]) -> float:
    return round(sum(component.score * component.weight for component in components), 1)


def get_overview(profile_id: str = "de") -> MarketOverview:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    cache_key = f"atlasiq:market:overview:{profile.id}:{profile.market_pack_id}:v{active_pack_version(profile.market_pack_id)}"
    cached = get_json(cache_key)
    if cached:
        return MarketOverview.model_validate(cached)
    components = components_for(component_configs=active_component_configs(profile.market_pack_id))
    score = weighted_score(components)
    overview = MarketOverview(
        market=profile.market_label,
        score=score,
        recommendation=recommendation_for(score),
        last_updated=iso_now(),
        components=components,
        metrics=METRICS,
        evidence=EVIDENCE,
    )
    set_json(cache_key, overview.model_dump(mode="json"), ttl_seconds=60)
    return overview


def run_configured_scenario(component_configs: list[dict[str, object]], scenario: ScenarioRequest) -> ScenarioResult:
    baseline = weighted_score(components_for(component_configs=component_configs))
    components = components_for(scenario, component_configs)
    score = weighted_score(components)
    movement = "上升" if score >= baseline else "下降"
    explanation = (
        f"在当前假设下，市场评分较基线{movement} {abs(score - baseline):.1f} 分。"
        "该结果用于比较假设敏感性，不构成投资建议。"
    )
    return ScenarioResult(
        score=score,
        delta=round(score - baseline, 1),
        recommendation=recommendation_for(score),
        component_scores=components,
        explanation=explanation,
    )


def run_scenario(scenario: ScenarioRequest, profile_id: str = "de") -> ScenarioResult:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    return run_configured_scenario(active_component_configs(profile.market_pack_id), scenario)


def sensitivity_analysis(scenario: ScenarioRequest, perturbation: float = 10, profile_id: str = "de") -> SensitivityResult:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    configs = active_component_configs(profile.market_pack_id)
    baseline_score = weighted_score(components_for(scenario, configs))
    items: list[SensitivityItem] = []
    for key, label, low, high in SENSITIVITY_DIMENSIONS:
        current_value = getattr(scenario, key)
        positive = scenario.model_copy(update={key: clamp(current_value + perturbation, low, high)})
        negative = scenario.model_copy(update={key: clamp(current_value - perturbation, low, high)})
        positive_delta = round(weighted_score(components_for(positive, configs)) - baseline_score, 1)
        negative_delta = round(weighted_score(components_for(negative, configs)) - baseline_score, 1)
        items.append(
            SensitivityItem(
                key=key,
                label=label,
                positive_delta=positive_delta,
                negative_delta=negative_delta,
                impact=max(abs(positive_delta), abs(negative_delta)),
            )
        )
    return SensitivityResult(
        baseline_score=baseline_score,
        perturbation=perturbation,
        items=sorted(items, key=lambda item: item.impact, reverse=True),
    )


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    remainder = index - lower
    return round(ordered[lower] * (1 - remainder) + ordered[upper] * remainder, 1)


def simulate_uncertainty(scenario: ScenarioRequest, iterations: int = 1200, seed: int = 42, profile_id: str = "de") -> SimulationResult:
    if iterations < 100 or iterations > 10000:
        raise ValueError("iterations must be between 100 and 10000")
    random = Random(seed)
    component_stddev = {"growth": 4.5, "resource": 3.5, "policy": 7.5, "demand": 5.5}
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    components = components_for(scenario, active_component_configs(profile.market_pack_id))
    scores: list[float] = []
    for _ in range(iterations):
        sample = [
            ScoreComponent(
                key=component.key,
                label=component.label,
                score=clamp(random.gauss(component.score, component_stddev.get(component.key, 5.0))),
                weight=component.weight,
                explanation=component.explanation,
            )
            for component in components
        ]
        scores.append(weighted_score(sample))
    p10 = percentile(scores, 0.1)
    p50 = percentile(scores, 0.5)
    p90 = percentile(scores, 0.9)
    probability = round(sum(score >= 75 for score in scores) / iterations, 3)
    return SimulationResult(
        iterations=iterations,
        p10=p10,
        p50=p50,
        p90=p90,
        probability_research=probability,
        explanation=(
            "在组件不确定性假设下，结果区间反映的是情景敏感性，不是对真实市场结果的概率承诺。"
            "达到 75 分“积极研究”阈值的比例用于比较当前假设下的稳健性。"
        ),
    )
