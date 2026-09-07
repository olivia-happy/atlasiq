from __future__ import annotations

from ..schemas import ExtractedEvent


RULES: tuple[tuple[str, tuple[str, ...], str, list[str], str], ...] = (
    ("grid", ("grid", "connection", "curtailment", "network", "interconnection", "delay", "wait time"), "negative", ["grid_absorption"], "Grid delivery or connection constraints require validation."),
    ("policy", ("policy", "regulation", "subsidy", "tariff", "permit", "law"), "mixed", ["policy_auction", "project_economics"], "Policy signal requires primary-source validation before decision use."),
    ("auction", ("auction", "tender", "bid", "procurement"), "positive", ["policy_auction", "market_growth"], "Auction activity is a market-access signal pending manual confirmation."),
    ("demand", ("demand", "deployment", "installation", "capacity", "electricity consumption"), "positive", ["market_growth", "power_demand"], "Demand signal indicates potential market pull, subject to structured data checks."),
    ("trade", ("trade", "import", "export", "supply chain", "module price", "anti-dumping"), "mixed", ["supply_trade", "project_economics"], "Trade and supply-chain conditions may change project economics."),
    ("finance", ("financing", "interest rate", "inflation", "currency", "fd i", "investment"), "mixed", ["macro_finance", "project_economics"], "Financing conditions are relevant but need structured macro confirmation."),
)


def extract_event_fields(title: str, summary: str) -> ExtractedEvent:
    text = f"{title} {summary}".lower()
    for event_type, keywords, direction, factors, explanation in RULES:
        if any(keyword in text for keyword in keywords):
            return ExtractedEvent(
                event_type=event_type,
                impact_direction=direction,
                impact_factors=factors,
                confidence=0.78,
                summary=explanation,
            )
    return ExtractedEvent(
        event_type="monitor",
        impact_direction="unknown",
        impact_factors=[],
        confidence=0.35,
        summary="Signal retained for monitoring; it does not change factor scores.",
    )
