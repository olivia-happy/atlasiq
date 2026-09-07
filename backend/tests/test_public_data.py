from app.services.countries import get_country_profile
from app.services.public_data import fetch_pvgis, fetch_world_bank


class FakeResponse:
    def __init__(self, payload: dict | list) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeClient:
    def get(self, url: str) -> FakeResponse:
        if "PVcalc" in url:
            return FakeResponse({"outputs": {"totals": {"fixed": {"E_y": 1820.5, "H(i)_y": 2100.0}}}})
        if "NY.GDP.MKTP.KD.ZG" in url:
            return FakeResponse([{}, [{"date": "2024", "value": 4.2}]])
        return FakeResponse([{}, [{"date": "2024", "value": None}]])


def test_pvgis_adapter_turns_response_into_profile_observations() -> None:
    observations = fetch_pvgis(get_country_profile("es"), client=FakeClient())

    assert {item.metric_key for item in observations} == {"annual_irradiation", "pv_yield"}
    assert all(item.profile_id == "es" for item in observations)


def test_world_bank_adapter_keeps_missing_values_missing() -> None:
    observations = fetch_world_bank(get_country_profile("sa"), client=FakeClient())

    assert next(item for item in observations if item.metric_key == "gdp_growth").value == 4.2
    assert next(item for item in observations if item.metric_key == "fdi_percent_gdp").value is None
