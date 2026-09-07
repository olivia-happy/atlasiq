from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Protocol

import httpx

from ..schemas import CountryProfile, RawObservation


class JsonClient(Protocol):
    def get(self, url: str) -> object: ...


WORLD_BANK_CODES = {"de": "DEU", "es": "ESP", "fr": "FRA", "ae": "ARE", "sa": "SAU"}
WORLD_BANK_INDICATORS = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "fdi_percent_gdp": "BX.KLT.DINV.WD.GD.ZS",
    "electricity_access": "EG.ELC.ACCS.ZS",
    "renewable_electricity_share": "EG.ELC.RNEW.ZS",
}


def fetched_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_pvgis(profile: CountryProfile | None, client: JsonClient | None = None) -> list[RawObservation]:
    if profile is None:
        raise ValueError("Country profile not found")
    response = (client or httpx.Client(timeout=25)).get(
        "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
        f"?lat={profile.latitude}&lon={profile.longitude}&peakpower=1&loss=14&outputformat=json"
    )
    response.raise_for_status()
    fixed = response.json()["outputs"]["totals"]["fixed"]
    now = fetched_at()
    payload = json.dumps(fixed)
    return [
        RawObservation(profile_id=profile.id, source_id="pvgis", metric_key="pv_yield", observed_at="latest", value=float(fixed["E_y"]), unit="kwh_kw", payload_json=payload, fetched_at=now),
        RawObservation(profile_id=profile.id, source_id="pvgis", metric_key="annual_irradiation", observed_at="latest", value=float(fixed["H(i)_y"]), unit="kwh_m2", payload_json=payload, fetched_at=now),
    ]


def fetch_world_bank(profile: CountryProfile | None, client: JsonClient | None = None) -> list[RawObservation]:
    if profile is None:
        raise ValueError("Country profile not found")
    api_client = client or httpx.Client(timeout=25)
    country_code = WORLD_BANK_CODES[profile.id]
    observations: list[RawObservation] = []
    now = fetched_at()
    for metric_key, indicator in WORLD_BANK_INDICATORS.items():
        response = api_client.get(f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator}?format=json&per_page=10")
        response.raise_for_status()
        rows = response.json()[1] if len(response.json()) > 1 else []
        latest = next((row for row in rows if row.get("value") is not None), rows[0] if rows else {})
        value = latest.get("value") if latest else None
        observations.append(RawObservation(
            profile_id=profile.id, source_id="world-bank", metric_key=metric_key,
            observed_at=str(latest.get("date") or "unknown"), value=float(value) if value is not None else None,
            unit="percent", status="observed" if value is not None else "missing",
            payload_json=json.dumps(latest), fetched_at=now,
        ))
    return observations
