from app.schemas import NewsItem, ScenarioRequest, SubscriptionRequest
from app.services.notifications import (
    clear_notification_state,
    create_subscription,
    dispatch_for_news,
    list_deliveries,
    send_report_email,
)
from app.services.reports import create_research_report


def test_immediate_medium_subscription_creates_safe_preview_for_high_signal() -> None:
    clear_notification_state()
    create_subscription(
        SubscriptionRequest(
            email="analyst@example.com",
            country="Germany",
            topic="photovoltaic",
            frequency="immediate",
            min_impact="medium",
        )
    )
    signal = NewsItem(
        id="N-high",
        title="Germany changes solar subsidy rules",
        category="Policy",
        impact="high",
        summary="Test signal",
        why="Policy change",
        source="Test",
        published_at="2026-08-17T09:00:00Z",
        acknowledged=False,
    )

    deliveries = dispatch_for_news([signal])

    assert len(deliveries) == 1
    assert deliveries[0].mode == "preview"
    assert deliveries[0].email == "analyst@example.com"
    assert list_deliveries()[0].news_id == "N-high"


def test_report_email_without_smtp_is_preview_and_never_constructs_a_client(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLASIQ_REPORT_DIR", str(tmp_path))
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    report = create_research_report("ae", ScenarioRequest())

    def unexpected_client(*_: object, **__: object) -> object:
        raise AssertionError("SMTP must not be constructed for a safety preview")

    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", unexpected_client)
    result = send_report_email(report.id, "analyst@example.com", ["docx", "pdf"])

    assert result.mode == "preview"
    assert result.attachments == [f"{report.id}.docx", f"{report.id}.pdf"]


def test_configured_smtp_sends_the_selected_report_attachment(tmp_path, monkeypatch) -> None:
    class FakeSmtp:
        message = None

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def send_message(self, message) -> None:
            self.message = message

    monkeypatch.setenv("ATLASIQ_REPORT_DIR", str(tmp_path))
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "atlas@example.test")
    report = create_research_report("sa", ScenarioRequest())
    smtp = FakeSmtp()
    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", lambda *_args, **_kwargs: smtp)

    result = send_report_email(report.id, "analyst@example.com", ["pdf"])

    assert result.mode == "sent"
    assert result.attachments == [f"{report.id}.pdf"]
    assert f'filename="{report.id}.pdf"' in smtp.message.as_string()
