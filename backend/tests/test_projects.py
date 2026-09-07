from fastapi.testclient import TestClient

from app.main import app
from app.schemas import EvidenceItemInput, ProjectCreateRequest, ProjectUpdateRequest, RawObservation
from app.services.feature_store import acknowledge_evidence, save_evidence, save_observations
from app.services.projects import assess_project, clear_project_state, create_project, get_project, list_project_tasks, list_projects, trigger_project_reassessment, update_project, update_project_task


client = TestClient(app)


def test_project_is_scoped_to_one_supported_country() -> None:
    clear_project_state()
    created = create_project(
        ProjectCreateRequest(
            name="Almería PV",
            profile_id="es",
            owner="Development EU",
        )
    )

    assert created.profile_id == "es"
    assert list_projects("de") == []
    assert [project.id for project in list_projects("es")] == [created.id]


def test_insufficient_grid_and_policy_create_blockers_and_tasks() -> None:
    clear_project_state()
    project = create_project(ProjectCreateRequest(name="Murcia PV", profile_id="es", owner="Development EU"))

    assessment = assess_project(project.id)

    assert assessment.verdict == "not_ready"
    assert {task.factor_key for task in list_project_tasks(project.id)} >= {"grid_absorption", "policy_auction"}


def test_reassessing_does_not_duplicate_open_factor_tasks() -> None:
    clear_project_state()
    project = create_project(ProjectCreateRequest(name="Valencia PV", profile_id="es", owner="Development EU"))
    save_observations("es", [
        RawObservation(profile_id="es", source_id="pvgis", metric_key="annual_irradiation", observed_at="latest", value=1900, unit="kwh_m2"),
        RawObservation(profile_id="es", source_id="pvgis", metric_key="pv_yield", observed_at="latest", value=1700, unit="kwh_kw"),
    ])

    assess_project(project.id)
    assess_project(project.id)

    assert len([task for task in list_project_tasks(project.id) if task.factor_key == "grid_absorption" and task.status == "open"]) == 1


def test_project_cannot_enter_review_until_blockers_are_closed() -> None:
    clear_project_state()
    project = create_project(ProjectCreateRequest(name="Seville PV", profile_id="es", owner="Development EU"))
    assess_project(project.id)

    try:
        update_project(project.id, ProjectUpdateRequest(stage="review"))
        assert False, "open blockers must prevent review"
    except ValueError as error:
        assert "blocker" in str(error)

    for task in list_project_tasks(project.id):
        if task.priority == "blocker":
            assert update_project_task(project.id, task.id, "done", "Validated for committee review") is not None

    transitioned = update_project(project.id, ProjectUpdateRequest(stage="review"))
    assert transitioned.stage == "review"


def test_project_api_creates_assessment_and_returns_tasks() -> None:
    clear_project_state()
    response = client.post("/api/projects", json={"name": "Riyadh PV", "profile_id": "sa", "owner": "MENA Development"})
    assert response.status_code == 201

    project_id = response.json()["id"]
    assessment = client.post(f"/api/projects/{project_id}/assessments")
    tasks = client.get(f"/api/projects/{project_id}/tasks")

    assert assessment.status_code == 200
    assert assessment.json()["project_id"] == project_id
    assert tasks.status_code == 200
    assert any(task["priority"] == "blocker" for task in tasks.json())


def test_confirmed_evidence_creates_one_review_task_without_changing_project_stage() -> None:
    clear_project_state()
    project = create_project(ProjectCreateRequest(name="Jeddah PV", profile_id="sa", owner="MENA Development"))
    evidence = save_evidence("sa", [
        EvidenceItemInput(
            title="Grid connection delay announced",
            source="Public grid feed",
            url="https://example.test/sa-project-grid",
            event_type="grid",
            impact_direction="negative",
            impact_factors=["grid_absorption"],
        )
    ])[0]
    acknowledge_evidence("sa", evidence.id)

    first = trigger_project_reassessment("sa", evidence.id)
    second = trigger_project_reassessment("sa", evidence.id)
    tasks = list_project_tasks(project.id)

    assert first == 1
    assert second == 0
    assert get_project(project.id).stage == "screening"
    review_tasks = [task for task in tasks if task.factor_key == "evidence_review:grid_absorption"]
    assert len(review_tasks) == 1
    assert review_tasks[0].priority == "high"


def test_project_briefing_uses_latest_assessment_tasks_and_evidence_ids() -> None:
    clear_project_state()
    project = create_project(ProjectCreateRequest(name="Madrid PV", profile_id="es", owner="Development EU"))
    assessment = assess_project(project.id)

    from app.services.projects import build_project_briefing

    briefing = build_project_briefing(project.id)

    assert briefing is not None
    assert project.name in briefing
    assert assessment.factor_snapshot_id in briefing
    assert "Due-diligence tasks" in briefing
    assert "Evidence IDs" in briefing
