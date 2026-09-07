import asyncio

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import news_poll_loop
from app.services.polling import news_poll_interval_seconds


client = TestClient(main.app)


def test_news_poll_interval_defaults_to_five_minutes_and_can_be_disabled(monkeypatch) -> None:
    monkeypatch.delenv("NEWS_POLL_INTERVAL_SECONDS", raising=False)
    assert news_poll_interval_seconds() == 300

    monkeypatch.setenv("NEWS_POLL_INTERVAL_SECONDS", "0")
    assert news_poll_interval_seconds() == 0

    monkeypatch.setenv("NEWS_POLL_INTERVAL_SECONDS", "not-a-number")
    assert news_poll_interval_seconds() == 300


def test_news_poll_loop_refreshes_once_then_stops_when_cancelled(monkeypatch) -> None:
    calls = {"sleep": 0, "refresh": 0}

    async def fake_sleep(_: int) -> None:
        calls["sleep"] += 1
        if calls["sleep"] > 1:
            raise asyncio.CancelledError

    async def fake_to_thread(callback):
        callback()

    def fake_refresh() -> None:
        calls["refresh"] += 1

    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(main, "refresh_live_news", fake_refresh)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(news_poll_loop(300))

    assert calls == {"sleep": 2, "refresh": 1}


def test_news_polling_status_endpoint_returns_the_active_interval(monkeypatch) -> None:
    monkeypatch.setenv("NEWS_POLL_INTERVAL_SECONDS", "120")

    response = client.get("/api/news/polling-status")

    assert response.status_code == 200
    assert response.json() == {"enabled": True, "interval_seconds": 120}
