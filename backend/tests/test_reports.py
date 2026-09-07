from __future__ import annotations

from pathlib import Path

from app.schemas import ScenarioRequest
from app.services.reports import create_research_report, get_research_report


def test_creates_markdown_docx_and_pdf_under_a_unique_report_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ATLASIQ_REPORT_DIR", str(tmp_path))

    report = create_research_report("fr", ScenarioRequest(demand_change=5))

    assert report.profile_id == "fr"
    assert report.market_pack_id == "fr-pv"
    assert "France" in report.markdown
    assert "P10 / P50 / P90" in report.markdown
    assert (tmp_path / f"{report.id}.docx").stat().st_size > 0
    assert (tmp_path / f"{report.id}.pdf").stat().st_size > 0
    assert get_research_report(report.id) == report


def test_report_ids_keep_historical_files_from_being_overwritten(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ATLASIQ_REPORT_DIR", str(tmp_path))

    first = create_research_report("es", ScenarioRequest())
    second = create_research_report("es", ScenarioRequest())

    assert first.id != second.id
    assert (tmp_path / f"{first.id}.pdf").exists()
    assert (tmp_path / f"{second.id}.pdf").exists()


def test_report_uses_one_factor_snapshot_for_coverage_and_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ATLASIQ_REPORT_DIR", str(tmp_path))

    report = create_research_report("es", ScenarioRequest())

    assert "Data coverage" in report.markdown
    assert "market_growth" in report.markdown
    assert "Evidence IDs" in report.markdown
