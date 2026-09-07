from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
from typing import Any

import httpx
from sqlalchemy import delete, select

from ..db import SourceAuditRecord, session_scope
from ..schemas import DataRefreshResult, OwidGermanySnapshot, PublicDataSource, WeatherSnapshot
from .countries import get_country_profile

OWID_ENERGY_URL = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"

SOURCE_DEFAULTS: dict[str, dict[str, str]] = {
    "owid-energy": {"status": "ready", "last_checked_at": None, "last_success_at": None, "observation_label": "待首次刷新"},
    "open-meteo": {"status": "ready", "last_checked_at": None, "last_success_at": None, "observation_label": "待首次刷新"},
}


SOURCE_DEFAULTS.update({
    "pvgis": {
        "status": "ready",
        "last_checked_at": None,
        "last_success_at": None,
        "observation_label": "Awaiting first PV potential refresh",
    },
    "world-bank": {
        "status": "ready",
        "last_checked_at": None,
        "last_success_at": None,
        "observation_label": "Awaiting first macro and energy refresh",
    },
})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_audit_key(profile_id: str, source_id: str) -> str:
    return f"{profile_id}:{source_id}"


def stored_source_audits(profile_id: str = "de") -> dict[str, SourceAuditRecord]:
    with session_scope() as session:
        records = session.scalars(select(SourceAuditRecord)).all()
    prefix = f"{profile_id}:"
    return {
        record.source_id.removeprefix(prefix): record
        for record in records
        if record.source_id.startswith(prefix)
    }


def clear_source_audits() -> None:
    with session_scope() as session:
        session.execute(delete(SourceAuditRecord))


def save_source_audits(profile_id: str, updates: dict[str, dict[str, str | None]]) -> None:
    with session_scope() as session:
        for source_id, audit in updates.items():
            audit_key = source_audit_key(profile_id, source_id)
            record = session.get(SourceAuditRecord, audit_key)
            if record is None:
                record = SourceAuditRecord(source_id=audit_key, **audit)
                session.add(record)
            else:
                record.status = audit["status"] or "ready"
                record.last_checked_at = audit["last_checked_at"]
                record.last_success_at = audit["last_success_at"]
                record.observation_label = audit["observation_label"] or "待首次刷新"


def list_public_sources(profile_id: str = "de") -> list[PublicDataSource]:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    audits = stored_source_audits(profile_id)
    owid_audit = audits.get("owid-energy")
    weather_audit = audits.get("open-meteo")
    owid_values = SOURCE_DEFAULTS["owid-energy"] if owid_audit is None else {
        "status": owid_audit.status,
        "last_checked_at": owid_audit.last_checked_at,
        "last_success_at": owid_audit.last_success_at,
        "observation_label": owid_audit.observation_label,
    }
    weather_values = SOURCE_DEFAULTS["open-meteo"] if weather_audit is None else {
        "status": weather_audit.status,
        "last_checked_at": weather_audit.last_checked_at,
        "last_success_at": weather_audit.last_success_at,
        "observation_label": weather_audit.observation_label,
    }
    source_items = [
        PublicDataSource(
            id="owid-energy",
            profile_id=profile_id,
            name="Our World in Data Energy",
            kind="energy",
            refresh_mode="manual",
            status=owid_values["status"],
            note=f"{profile.name} 年度太阳能装机与发电数据；用户触发刷新时下载并解析。",
            last_checked_at=owid_values["last_checked_at"],
            last_success_at=owid_values["last_success_at"],
            observation_label=owid_values["observation_label"] or "待首次刷新",
        ),
        PublicDataSource(
            id="open-meteo",
            profile_id=profile_id,
            name="Open-Meteo",
            kind="weather",
            refresh_mode="manual",
            status=weather_values["status"],
            note=f"{profile.name} 未来七日天气与短波辐照摘要；不需要付费密钥。",
            last_checked_at=weather_values["last_checked_at"],
            last_success_at=weather_values["last_success_at"],
            observation_label=weather_values["observation_label"] or "待首次刷新",
        ),
    ]
    for source_id, name, note in (
        (
            "pvgis",
            "PVGIS",
            f"European Commission PVGIS point estimate for {profile.name}: annual irradiation and PV yield, no API key required.",
        ),
        (
            "world-bank",
            "World Bank Open Data",
            f"World Bank country indicators for {profile.name}: GDP growth, FDI, electricity access and renewable-electricity share.",
        ),
    ):
        audit = audits.get(source_id)
        values = SOURCE_DEFAULTS[source_id] if audit is None else {
            "status": audit.status,
            "last_checked_at": audit.last_checked_at,
            "last_success_at": audit.last_success_at,
            "observation_label": audit.observation_label,
        }
        source_items.append(PublicDataSource(
            id=source_id,
            profile_id=profile_id,
            name=name,
            kind="energy",
            refresh_mode="manual",
            status=values["status"],
            note=note,
            last_checked_at=values["last_checked_at"],
            last_success_at=values["last_success_at"],
            observation_label=values["observation_label"] or SOURCE_DEFAULTS[source_id]["observation_label"],
        ))
    return source_items


def number(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def optional_number(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def parse_owid_snapshot(csv_text: str, country: str) -> OwidGermanySnapshot:
    rows = list(csv.DictReader(StringIO(csv_text)))
    filtered = [row for row in rows if row.get("country") == country and row.get("year")]
    if not filtered:
        raise ValueError(f"OWID energy data did not contain {country} rows")
    filtered.sort(key=lambda row: int(row["year"]))
    latest = filtered[-1]
    return OwidGermanySnapshot(
        country=country,
        records=len(filtered),
        latest_year=int(latest["year"]),
        solar_capacity_gw=optional_number(latest.get("solar_capacity")),
        solar_electricity_twh=number(latest.get("solar_electricity")),
    )


def parse_owid_germany_snapshot(csv_text: str) -> OwidGermanySnapshot:
    return parse_owid_snapshot(csv_text, "Germany")


def open_meteo_url(latitude: float, longitude: float, timezone_name: str) -> str:
    return (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&daily=temperature_2m_mean,shortwave_radiation_sum&forecast_days=7"
        f"&timezone={timezone_name}"
    )


def parse_open_meteo_snapshot(payload: dict[str, Any]) -> WeatherSnapshot:
    daily = payload.get("daily", {})
    temperatures = daily.get("temperature_2m_mean", [])
    radiation = daily.get("shortwave_radiation_sum", [])
    if not temperatures or len(temperatures) != len(radiation):
        raise ValueError("Open-Meteo response did not contain matching daily weather series")
    return WeatherSnapshot(
        days=len(temperatures),
        average_temperature_c=round(sum(float(item) for item in temperatures) / len(temperatures), 1),
        average_radiation_mj_m2=round(sum(float(item) for item in radiation) / len(radiation), 1),
    )


def refresh_public_snapshots(profile_id: str = "de") -> DataRefreshResult:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    checked_at = now_iso()
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            owid_response = client.get(OWID_ENERGY_URL)
            owid_response.raise_for_status()
            weather_response = client.get(open_meteo_url(profile.latitude, profile.longitude, profile.timezone))
            weather_response.raise_for_status()
        owid = parse_owid_snapshot(owid_response.text, profile.name)
        weather = parse_open_meteo_snapshot(weather_response.json())
        save_source_audits(profile_id, {
            "owid-energy": {
            "status": "live",
            "last_checked_at": checked_at,
            "last_success_at": checked_at,
            "observation_label": f"{owid.latest_year} 年度能源观测",
            },
            "open-meteo": {
            "status": "live",
            "last_checked_at": checked_at,
            "last_success_at": checked_at,
            "observation_label": f"未来 {weather.days} 日天气预测",
            },
        })
        return DataRefreshResult(
            status="live",
            owid=owid,
            weather=weather,
            message=f"已从配置的公开数据源刷新 {profile.name} 能源与天气摘要。",
        )
    except (httpx.HTTPError, ValueError) as error:
        existing = stored_source_audits(profile_id)
        save_source_audits(profile_id, {
            source_id: {
                "status": "degraded",
                "last_checked_at": checked_at,
                "last_success_at": existing.get(source_id).last_success_at if source_id in existing else None,
                "observation_label": existing.get(source_id).observation_label if source_id in existing else SOURCE_DEFAULTS[source_id]["observation_label"],
            }
            for source_id in SOURCE_DEFAULTS
        })
        return DataRefreshResult(
            status="degraded",
            message=f"{profile.name} 公开数据刷新失败，保留上次成功状态：{error}",
        )
