import sqlite3

from fastapi.testclient import TestClient

from app.main import app
from app.services import sources
from app.services.sources import clear_source_audits, list_public_sources, parse_owid_germany_snapshot, refresh_public_snapshots


client = TestClient(app)


def test_parse_owid_snapshot_filters_germany_and_keeps_latest_capacity() -> None:
    csv_text = """country,year,solar_capacity,solar_electricity
France,2025,35.0,42.0
Germany,2024,98.5,61.0
Germany,2025,109.0,70.0
"""

    snapshot = parse_owid_germany_snapshot(csv_text)

    assert snapshot.country == "Germany"
    assert snapshot.records == 2
    assert snapshot.latest_year == 2025
    assert snapshot.solar_capacity_gw == 109.0
    assert snapshot.solar_electricity_twh == 70.0


def test_parse_owid_snapshot_does_not_convert_missing_capacity_to_zero() -> None:
    csv_text = """country,year,solar_electricity
Germany,2025,89.62
"""

    snapshot = parse_owid_germany_snapshot(csv_text)

    assert snapshot.solar_capacity_gw is None


def test_data_sources_endpoint_exposes_refreshable_public_sources() -> None:
    response = client.get("/api/data-sources")

    assert response.status_code == 200
    source_names = {item["name"] for item in response.json()}
    assert "Our World in Data Energy" in source_names
    assert "Open-Meteo" in source_names
    assert "PVGIS" in source_names
    assert "World Bank Open Data" in source_names


def test_data_sources_endpoint_honors_country_query_parameter() -> None:
    response = client.get("/api/data-sources?profile_id=sa")

    assert response.status_code == 200
    assert {item["profile_id"] for item in response.json()} == {"sa"}


def test_public_source_metadata_records_check_and_success_times(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str = "", payload: dict | None = None) -> None:
            self.text = text
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload or {}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            if "owid" in url:
                return FakeResponse("country,year,solar_electricity\nGermany,2025,89.62\n")
            return FakeResponse(
                payload={
                    "daily": {
                        "temperature_2m_mean": [20, 19, 18, 21, 22, 20, 19],
                        "shortwave_radiation_sum": [18, 17, 16, 19, 20, 18, 17],
                    }
                }
            )

    monkeypatch.setattr(sources.httpx, "Client", FakeClient)

    result = refresh_public_snapshots()
    source_by_id = {source.id: source for source in list_public_sources()}

    assert result.status == "live"
    assert source_by_id["owid-energy"].last_checked_at is not None
    assert source_by_id["owid-energy"].last_success_at is not None
    assert source_by_id["owid-energy"].observation_label == "2025 年度能源观测"
    assert source_by_id["open-meteo"].observation_label == "未来 7 日天气预测"

    with sqlite3.connect("atlasiq-test.db") as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "source_audits" in tables
        persisted = connection.execute(
            "SELECT status, last_success_at FROM source_audits WHERE source_id = ?", ("de:owid-energy",)
        ).fetchone()
    assert persisted is not None
    assert persisted[0] == "live"
    assert persisted[1] is not None


def test_source_audits_are_isolated_by_country_profile(monkeypatch) -> None:
    class FakeResponse:
        text = "country,year,solar_capacity,solar_electricity\nSpain,2025,40.0,55.0\n"

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "daily": {
                    "temperature_2m_mean": [25, 24],
                    "shortwave_radiation_sum": [23, 21],
                }
            }

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, _: str) -> FakeResponse:
            return FakeResponse()

    clear_source_audits()
    monkeypatch.setattr(sources.httpx, "Client", FakeClient)

    result = refresh_public_snapshots("es")
    spanish_sources = list_public_sources("es")
    german_sources = list_public_sources("de")

    assert result.owid is not None
    assert result.owid.country == "Spain"
    assert spanish_sources[0].profile_id == "es"
    assert spanish_sources[0].last_success_at is not None
    assert german_sources[0].last_success_at is None
