from __future__ import annotations

import json

from sqlalchemy import select

from ..data import iso_now
from ..db import MarketPackVersionRecord, session_scope
from ..schemas import MarketPackDetail, MarketPackDraftRequest, MarketPackExport, MarketPackImportRequest, MarketPackSummary


DEFAULT_PACK = {
    "id": "de-pv",
    "version": 1,
    "status": "published",
    "name": "Germany Photovoltaic Entry Research",
    "country": "Germany",
    "sector": "Photovoltaic",
    "change_note": "Seeded baseline pack for the AtlasIQ local demonstration.",
}

COUNTRY_PACKS = {
    "de-pv": DEFAULT_PACK,
    "es-pv": {
        "id": "es-pv", "version": 1, "status": "published", "name": "Spain Photovoltaic Entry Research",
        "country": "Spain", "sector": "Photovoltaic", "change_note": "Seeded baseline pack for Spain local demonstration.",
    },
    "fr-pv": {
        "id": "fr-pv", "version": 1, "status": "published", "name": "France Photovoltaic Entry Research",
        "country": "France", "sector": "Photovoltaic", "change_note": "Seeded baseline pack for France local demonstration.",
    },
    "ae-pv": {
        "id": "ae-pv", "version": 1, "status": "published", "name": "UAE Photovoltaic Entry Research",
        "country": "United Arab Emirates", "sector": "Photovoltaic", "change_note": "Seeded baseline pack for UAE local demonstration.",
    },
    "sa-pv": {
        "id": "sa-pv", "version": 1, "status": "published", "name": "Saudi Arabia Photovoltaic Entry Research",
        "country": "Saudi Arabia", "sector": "Photovoltaic", "change_note": "Seeded baseline pack for Saudi Arabia local demonstration.",
    },
}

DEFAULT_COMPONENTS = (
    {
        "key": "growth",
        "label": "Market growth",
        "base_score": 82.0,
        "weight": 0.35,
        "explanation": "Installed capacity in the public baseline continues to grow.",
    },
    {
        "key": "resource",
        "label": "Resource conditions",
        "base_score": 76.0,
        "weight": 0.20,
        "explanation": "Weather and resource conditions are stable but require site-level validation.",
    },
    {
        "key": "policy",
        "label": "Policy certainty",
        "base_score": 64.0,
        "weight": 0.25,
        "explanation": "Policy variables remain uncertain and need formal due diligence.",
    },
    {
        "key": "demand",
        "label": "Demand and grid",
        "base_score": 71.0,
        "weight": 0.20,
        "explanation": "Demand is above baseline while grid delivery needs continuous monitoring.",
    },
)

COUNTRY_COMPONENTS = {
    "de-pv": DEFAULT_COMPONENTS,
    "es-pv": (
        {**DEFAULT_COMPONENTS[0], "base_score": 78.0}, {**DEFAULT_COMPONENTS[1], "base_score": 84.0},
        {**DEFAULT_COMPONENTS[2], "base_score": 68.0}, {**DEFAULT_COMPONENTS[3], "base_score": 69.0},
    ),
    "fr-pv": (
        {**DEFAULT_COMPONENTS[0], "base_score": 72.0}, {**DEFAULT_COMPONENTS[1], "base_score": 73.0},
        {**DEFAULT_COMPONENTS[2], "base_score": 71.0}, {**DEFAULT_COMPONENTS[3], "base_score": 67.0},
    ),
    "ae-pv": (
        {**DEFAULT_COMPONENTS[0], "base_score": 79.0}, {**DEFAULT_COMPONENTS[1], "base_score": 92.0},
        {**DEFAULT_COMPONENTS[2], "base_score": 66.0}, {**DEFAULT_COMPONENTS[3], "base_score": 70.0},
    ),
    "sa-pv": (
        {**DEFAULT_COMPONENTS[0], "base_score": 76.0}, {**DEFAULT_COMPONENTS[1], "base_score": 89.0},
        {**DEFAULT_COMPONENTS[2], "base_score": 63.0}, {**DEFAULT_COMPONENTS[3], "base_score": 68.0},
    ),
}


def ensure_default_market_pack() -> None:
    with session_scope() as session:
        now = iso_now()
        for pack_id, pack in COUNTRY_PACKS.items():
            if session.get(MarketPackVersionRecord, f"MPV-{pack_id}-v1") is not None:
                continue
            session.add(
                MarketPackVersionRecord(
                    id=f"MPV-{pack_id}-v1",
                    pack_id=pack_id,
                    version=1,
                    status="published",
                    name=pack["name"],
                    country=pack["country"],
                    sector=pack["sector"],
                    config_json=json.dumps({"schema_version": 1, "components": COUNTRY_COMPONENTS[pack_id]}),
                    change_note=pack["change_note"],
                    created_at=now,
                    published_at=now,
                )
            )


def _components_from_config(config_json: str, pack_id: str = "de-pv") -> list[dict[str, object]]:
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError:
        config = {}
    components = config.get("components") if isinstance(config, dict) else None
    if not isinstance(components, list) or not components:
        return [dict(component) for component in COUNTRY_COMPONENTS.get(pack_id, DEFAULT_COMPONENTS)]
    return [dict(component) for component in components if isinstance(component, dict)] or [dict(component) for component in COUNTRY_COMPONENTS.get(pack_id, DEFAULT_COMPONENTS)]


def active_component_configs(pack_id: str = "de-pv") -> list[dict[str, object]]:
    ensure_default_market_pack()
    with session_scope() as session:
        record = session.scalar(
            select(MarketPackVersionRecord)
            .where(MarketPackVersionRecord.pack_id == pack_id, MarketPackVersionRecord.status == "published")
            .order_by(MarketPackVersionRecord.version.desc())
        )
        if record is None:
            return [dict(component) for component in DEFAULT_COMPONENTS]
        return _components_from_config(record.config_json, pack_id)


def active_pack_version(pack_id: str = "de-pv") -> int:
    ensure_default_market_pack()
    with session_scope() as session:
        version = session.scalar(
            select(MarketPackVersionRecord.version)
            .where(MarketPackVersionRecord.pack_id == pack_id, MarketPackVersionRecord.status == "published")
            .order_by(MarketPackVersionRecord.version.desc())
        )
        return version or 1


def list_market_packs() -> list[MarketPackSummary]:
    ensure_default_market_pack()
    with session_scope() as session:
        records = session.scalars(
            select(MarketPackVersionRecord).order_by(MarketPackVersionRecord.pack_id, MarketPackVersionRecord.version.desc())
        ).all()
    return [
        MarketPackSummary(
            id=record.pack_id,
            version=record.version,
            status=record.status,
            name=record.name,
            country=record.country,
            sector=record.sector,
            change_note=record.change_note,
            created_at=record.created_at,
            published_at=record.published_at,
        )
        for record in records
    ]


def get_market_pack_version(pack_id: str, version: int) -> MarketPackDetail | None:
    ensure_default_market_pack()
    with session_scope() as session:
        record = session.scalar(
            select(MarketPackVersionRecord).where(
                MarketPackVersionRecord.pack_id == pack_id,
                MarketPackVersionRecord.version == version,
            )
        )
        if record is None:
            return None
        return MarketPackDetail(
            id=record.pack_id,
            version=record.version,
            status=record.status,
            name=record.name,
            country=record.country,
            sector=record.sector,
            change_note=record.change_note,
            created_at=record.created_at,
            published_at=record.published_at,
            components=_components_from_config(record.config_json, record.pack_id),
        )


def export_market_pack_version(pack_id: str, version: int) -> MarketPackExport | None:
    detail = get_market_pack_version(pack_id, version)
    if detail is None:
        return None
    return MarketPackExport(
        exported_at=iso_now(),
        source=detail,
        template=MarketPackDraftRequest(
            name=detail.name,
            country=detail.country,
            sector=detail.sector,
            change_note=detail.change_note,
            components=detail.components,
        ),
    )


def import_market_pack(request: MarketPackImportRequest) -> MarketPackSummary:
    return create_draft(request.pack_id, request.template)


def create_draft(pack_id: str, request: MarketPackDraftRequest) -> MarketPackSummary:
    component_keys = [component.key for component in request.components]
    if len(component_keys) != len(set(component_keys)):
        raise ValueError("Component keys must be unique")
    if abs(sum(component.weight for component in request.components) - 1) > 0.0001:
        raise ValueError("Component weights must sum to 1")
    ensure_default_market_pack()
    with session_scope() as session:
        highest_version = session.scalars(
            select(MarketPackVersionRecord.version)
            .where(MarketPackVersionRecord.pack_id == pack_id)
            .order_by(MarketPackVersionRecord.version.desc())
        ).first() or 0
        record = MarketPackVersionRecord(
            id=f"MPV-{pack_id}-v{highest_version + 1}",
            pack_id=pack_id,
            version=highest_version + 1,
            status="draft",
            name=request.name,
            country=request.country,
            sector=request.sector,
            config_json=json.dumps({"components": [component.model_dump() for component in request.components]}),
            change_note=request.change_note,
            created_at=iso_now(),
            published_at=None,
        )
        session.add(record)
        session.flush()
        return MarketPackSummary(
            id=record.pack_id,
            version=record.version,
            status=record.status,
            name=record.name,
            country=record.country,
            sector=record.sector,
            change_note=record.change_note,
            created_at=record.created_at,
            published_at=record.published_at,
        )


def publish_draft(pack_id: str, version: int) -> MarketPackSummary | None:
    with session_scope() as session:
        draft = session.scalar(
            select(MarketPackVersionRecord).where(
                MarketPackVersionRecord.pack_id == pack_id,
                MarketPackVersionRecord.version == version,
                MarketPackVersionRecord.status == "draft",
            )
        )
        if draft is None:
            return None
        for previous in session.scalars(
            select(MarketPackVersionRecord).where(
                MarketPackVersionRecord.pack_id == pack_id,
                MarketPackVersionRecord.status == "published",
            )
        ).all():
            previous.status = "archived"
        draft.status = "published"
        draft.published_at = iso_now()
        session.flush()
        return MarketPackSummary(
            id=draft.pack_id,
            version=draft.version,
            status=draft.status,
            name=draft.name,
            country=draft.country,
            sector=draft.sector,
            change_note=draft.change_note,
            created_at=draft.created_at,
            published_at=draft.published_at,
        )
