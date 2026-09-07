from __future__ import annotations

from datetime import datetime, timezone


METRICS = [
    {"month": "2025-09", "opportunity": 63.0, "capacity_gw": 102.0, "demand_index": 98.0},
    {"month": "2025-10", "opportunity": 64.5, "capacity_gw": 103.2, "demand_index": 99.0},
    {"month": "2025-11", "opportunity": 65.1, "capacity_gw": 104.1, "demand_index": 100.0},
    {"month": "2025-12", "opportunity": 66.0, "capacity_gw": 105.6, "demand_index": 101.0},
    {"month": "2026-01", "opportunity": 67.4, "capacity_gw": 107.0, "demand_index": 102.0},
    {"month": "2026-02", "opportunity": 68.1, "capacity_gw": 108.5, "demand_index": 103.0},
    {"month": "2026-03", "opportunity": 69.0, "capacity_gw": 109.8, "demand_index": 102.0},
    {"month": "2026-04", "opportunity": 70.2, "capacity_gw": 111.3, "demand_index": 104.0},
    {"month": "2026-05", "opportunity": 71.0, "capacity_gw": 112.6, "demand_index": 106.0},
    {"month": "2026-06", "opportunity": 72.4, "capacity_gw": 114.0, "demand_index": 107.0},
]

EVIDENCE = [
    {
        "id": "D1",
        "title": "Germany solar capacity trajectory",
        "source": "AtlasIQ public-energy demo snapshot",
        "excerpt": "Installed photovoltaic capacity increased across the displayed monthly sample, supporting the market-growth component.",
        "metric": "capacity_gw",
    },
    {
        "id": "D2",
        "title": "Demand and grid-context indicator",
        "source": "AtlasIQ public-energy demo snapshot",
        "excerpt": "The demand index remained above the 2025 baseline in the latest observation, while variability remains a material execution risk.",
        "metric": "demand_index",
    },
    {
        "id": "D3",
        "title": "Policy uncertainty note",
        "source": "User-curated public policy brief",
        "excerpt": "Support-mechanism changes can affect the timing and economics of new photovoltaic projects; this is represented as a scenario variable rather than a factual forecast.",
        "metric": "policy",
    },
]

NEWS_ITEMS = [
    {
        "id": "N1",
        "title": "Grid connection discussion added to Germany watchlist",
        "category": "Grid risk",
        "impact": "medium",
        "summary": "A source-configured monitoring item was added for grid connection timing. It is a demo signal and requires analyst verification before changing a decision.",
        "why": "It may affect the execution-risk component of the Germany opportunity score.",
        "source": "AtlasIQ seed news",
        "published_at": "2026-08-17T08:30:00Z",
        "acknowledged": False,
    },
    {
        "id": "N2",
        "title": "Solar-demand trend remains on the analyst watchlist",
        "category": "Demand",
        "impact": "low",
        "summary": "The latest sample data keeps demand conditions above the baseline. This card demonstrates digest-style monitoring, not a live market claim.",
        "why": "It supports the demand component but does not independently change the recommendation.",
        "source": "AtlasIQ seed news",
        "published_at": "2026-08-16T15:00:00Z",
        "acknowledged": False,
    },
]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
