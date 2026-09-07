from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from sqlalchemy import select

from ..data import iso_now
from ..db import EvidenceRecord, FactorSnapshotRecord, RawObservationRecord, session_scope
from ..schemas import EvidenceItem, EvidenceItemInput, FactorSnapshot, RawObservation


def observation_id(observation: RawObservation) -> str:
    value = "|".join([observation.profile_id, observation.source_id, observation.metric_key, observation.observed_at])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def save_observations(profile_id: str, observations: list[RawObservation]) -> list[RawObservation]:
    saved: list[RawObservation] = []
    with session_scope() as session:
        for observation in observations:
            if observation.profile_id != profile_id:
                raise ValueError("Observation profile does not match target profile")
            record_id = observation_id(observation)
            record = session.get(RawObservationRecord, record_id)
            if record is None:
                record = RawObservationRecord(id=record_id, **observation.model_dump())
                session.add(record)
            else:
                record.value = observation.value
                record.status = observation.status
                record.payload_json = observation.payload_json
                record.fetched_at = observation.fetched_at
            saved.append(observation)
    return saved


def list_observations(profile_id: str, metric_key: str | None = None) -> list[RawObservation]:
    with session_scope() as session:
        query = select(RawObservationRecord).where(RawObservationRecord.profile_id == profile_id)
        if metric_key:
            query = query.where(RawObservationRecord.metric_key == metric_key)
        records = session.scalars(query.order_by(RawObservationRecord.observed_at.desc())).all()
    return [RawObservation.model_validate(record, from_attributes=True) for record in records]


def evidence_id(profile_id: str, item: EvidenceItemInput) -> str:
    identity = item.url or f"{item.source}|{item.title}|{item.published_at or ''}"
    return f"EV-{profile_id}-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def to_evidence(record: EvidenceRecord) -> EvidenceItem:
    return EvidenceItem(
        id=record.id,
        profile_id=record.profile_id,
        title=record.title,
        source=record.source,
        url=record.url,
        summary=record.summary,
        excerpt=record.excerpt,
        published_at=record.published_at,
        language=record.language,
        category=record.category,
        event_type=record.event_type,
        impact_direction=record.impact_direction,
        impact_factors=json.loads(record.impact_factors_json),
        confidence=record.confidence,
        extraction_mode=record.extraction_mode,
        acknowledged=record.acknowledged,
        created_at=record.created_at,
    )


def save_evidence(profile_id: str, items: list[EvidenceItemInput]) -> list[EvidenceItem]:
    saved: list[EvidenceItem] = []
    with session_scope() as session:
        for item in items:
            record_id = evidence_id(profile_id, item)
            record = session.get(EvidenceRecord, record_id)
            if record is None:
                record = EvidenceRecord(
                    id=record_id, profile_id=profile_id, title=item.title, source=item.source, url=item.url,
                    summary=item.summary[:2000], excerpt=item.excerpt[:1200], published_at=item.published_at,
                    language=item.language, category=item.category, event_type=item.event_type,
                    impact_direction=item.impact_direction, impact_factors_json=json.dumps(item.impact_factors),
                    confidence=item.confidence, extraction_mode=item.extraction_mode, created_at=iso_now(),
                )
                session.add(record)
                session.flush()
            saved.append(to_evidence(record))
    return saved


def list_evidence(profile_id: str, limit: int = 100) -> list[EvidenceItem]:
    with session_scope() as session:
        records = session.scalars(
            select(EvidenceRecord).where(EvidenceRecord.profile_id == profile_id).order_by(EvidenceRecord.created_at.desc()).limit(limit)
        ).all()
    return [to_evidence(record) for record in records]


def acknowledge_evidence(profile_id: str, evidence_id: str) -> EvidenceItem | None:
    with session_scope() as session:
        record = session.get(EvidenceRecord, evidence_id)
        if record is None or record.profile_id != profile_id:
            return None
        record.acknowledged = True
        session.flush()
        return to_evidence(record)


def save_factor_snapshot(snapshot: FactorSnapshot) -> FactorSnapshot:
    with session_scope() as session:
        session.add(FactorSnapshotRecord(
            id=snapshot.id or f"FS-{uuid4().hex[:16]}", profile_id=snapshot.profile_id,
            market_pack_id=snapshot.market_pack_id, market_pack_version=snapshot.market_pack_version,
            captured_at=snapshot.captured_at, items_json=json.dumps([item.model_dump() for item in snapshot.items]),
        ))
    return snapshot


def latest_factor_snapshot(profile_id: str) -> FactorSnapshot | None:
    with session_scope() as session:
        record = session.scalar(
            select(FactorSnapshotRecord).where(FactorSnapshotRecord.profile_id == profile_id).order_by(FactorSnapshotRecord.captured_at.desc())
        )
    if record is None:
        return None
    return FactorSnapshot(
        id=record.id, profile_id=record.profile_id, market_pack_id=record.market_pack_id,
        market_pack_version=record.market_pack_version, captured_at=record.captured_at, items=json.loads(record.items_json),
    )
