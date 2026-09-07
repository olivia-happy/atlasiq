from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_market_packs_endpoint_seeds_a_published_germany_photovoltaic_pack() -> None:
    response = client.get("/api/market-packs")

    assert response.status_code == 200
    pack = next(item for item in response.json() if item["id"] == "de-pv")
    assert pack["version"] == 1
    assert pack["status"] == "published"
    assert pack["country"] == "Germany"
    assert pack["sector"] == "Photovoltaic"


def test_market_pack_draft_rejects_component_weights_that_do_not_sum_to_one() -> None:
    response = client.post(
        "/api/market-packs/de-pv/drafts",
        json={
            "name": "Germany PV draft",
            "country": "Germany",
            "sector": "Photovoltaic",
            "change_note": "Validate weights before allowing a publish review.",
            "components": [
                {"key": "growth", "label": "Growth", "base_score": 80, "weight": 0.5},
                {"key": "grid", "label": "Grid", "base_score": 70, "weight": 0.2},
            ],
        },
    )

    assert response.status_code == 422
    assert "sum to 1" in response.json()["detail"]


def test_market_pack_can_publish_a_valid_draft_without_overwriting_the_old_version() -> None:
    draft = client.post(
        "/api/market-packs/de-pv/drafts",
        json={
            "name": "Germany PV draft",
            "country": "Germany",
            "sector": "Photovoltaic",
            "change_note": "Publish a reviewed version rather than editing the live pack.",
            "components": [
                {"key": "growth", "label": "Growth", "base_score": 80, "weight": 0.4},
                {"key": "grid", "label": "Grid", "base_score": 70, "weight": 0.3},
                {"key": "policy", "label": "Policy", "base_score": 65, "weight": 0.3},
            ],
        },
    )

    published = client.post(f"/api/market-packs/de-pv/versions/{draft.json()['version']}/publish")

    assert draft.status_code == 201
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["version"] == draft.json()["version"]
    assert client.get("/api/market/overview").json()["score"] == 72.5


def test_market_pack_version_exposes_its_immutable_component_configuration() -> None:
    draft = client.post(
        "/api/market-packs/de-pv/drafts",
        json={
            "name": "Germany PV component review",
            "country": "Germany",
            "sector": "Photovoltaic",
            "change_note": "Expose the reviewable configuration before publication.",
            "components": [
                {"key": "growth", "label": "Growth", "base_score": 81, "weight": 0.5},
                {"key": "resource", "label": "Resource", "base_score": 73, "weight": 0.25},
                {"key": "policy", "label": "Policy", "base_score": 62, "weight": 0.25},
            ],
        },
    )

    response = client.get(f"/api/market-packs/de-pv/versions/{draft.json()['version']}")

    assert draft.status_code == 201
    assert response.status_code == 200
    assert response.json()["version"] == draft.json()["version"]
    assert response.json()["components"] == [
        {"key": "growth", "label": "Growth", "base_score": 81.0, "weight": 0.5},
        {"key": "resource", "label": "Resource", "base_score": 73.0, "weight": 0.25},
        {"key": "policy", "label": "Policy", "base_score": 62.0, "weight": 0.25},
    ]


def test_market_pack_template_can_be_exported_and_imported_as_a_new_draft() -> None:
    exported = client.get("/api/market-packs/de-pv/versions/1/export")

    imported = client.post(
        "/api/market-packs/imports",
        json={
            "pack_id": "es-pv",
            "template": {
                "name": "Spain photovoltaic entry research",
                "country": "Spain",
                "sector": "Photovoltaic",
                "change_note": "Imported from a reviewed Germany template and adapted for Spain.",
                "components": [
                    {"key": "growth", "label": "Growth", "base_score": 76, "weight": 0.35},
                    {"key": "resource", "label": "Resource", "base_score": 82, "weight": 0.20},
                    {"key": "policy", "label": "Policy", "base_score": 70, "weight": 0.25},
                    {"key": "demand", "label": "Demand", "base_score": 68, "weight": 0.20},
                ],
            },
        },
    )

    assert exported.status_code == 200
    assert exported.json()["format_version"] == 1
    assert exported.json()["template"]["name"] == "Germany Photovoltaic Entry Research"
    assert imported.status_code == 201
    assert imported.json()["id"] == "es-pv"
    assert imported.json()["version"] == 2
    assert imported.json()["status"] == "draft"


def test_market_pack_draft_can_be_scored_in_a_sandbox_without_publishing() -> None:
    draft = client.post(
        "/api/market-packs/preview-pv/drafts",
        json={
            "name": "Preview-only photovoltaic template",
            "country": "Template country",
            "sector": "Photovoltaic",
            "change_note": "Run the shared scenario model without changing the live market overview.",
            "components": [
                {"key": "growth", "label": "Growth", "base_score": 76, "weight": 0.35},
                {"key": "resource", "label": "Resource", "base_score": 82, "weight": 0.20},
                {"key": "policy", "label": "Policy", "base_score": 70, "weight": 0.25},
                {"key": "demand", "label": "Demand", "base_score": 68, "weight": 0.20},
            ],
        },
    )

    preview = client.post(
        f"/api/market-packs/preview-pv/versions/{draft.json()['version']}/preview",
        json={"demand_change": 10},
    )

    assert draft.status_code == 201
    assert preview.status_code == 200
    assert preview.json()["mode"] == "sandbox"
    assert preview.json()["pack_id"] == "preview-pv"
    assert preview.json()["version"] == draft.json()["version"]
    assert preview.json()["score"] == 75.0
    assert preview.json()["delta"] == 0.9
