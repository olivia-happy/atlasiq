from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_lists_five_country_profiles_with_independent_market_packs() -> None:
    response = client.get("/api/countries")

    assert response.status_code == 200
    profiles = response.json()
    assert [item["id"] for item in profiles] == ["de", "es", "fr", "ae", "sa"]
    assert [item["name"] for item in profiles] == ["Germany", "Spain", "France", "United Arab Emirates", "Saudi Arabia"]
    assert [item["display_name"] for item in profiles] == ["德国", "西班牙", "法国", "阿联酋", "沙特阿拉伯"]
    assert [item["market_label"] for item in profiles] == ["德国光伏市场", "西班牙光伏市场", "法国光伏市场", "阿联酋光伏市场", "沙特阿拉伯光伏市场"]
    assert profiles[0]["market_pack_id"] == "de-pv"
    assert profiles[1]["market_pack_id"] == "es-pv"


def test_country_workspace_uses_the_selected_profile_published_pack() -> None:
    response = client.get("/api/countries/es/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["id"] == "es"
    assert payload["market_pack"]["id"] == "es-pv"
    assert payload["overview"]["market"] == "西班牙光伏市场"
    assert len(payload["features"]["items"]) == 8
    assert payload["impact_matrix"]["profile_id"] == "es"
    assert payload["evidence_timeline"] == []


def test_unknown_country_does_not_fall_back_to_germany() -> None:
    response = client.get("/api/countries/no-such-country/workspace")

    assert response.status_code == 404
    assert response.json()["detail"] == "Country profile not found"
