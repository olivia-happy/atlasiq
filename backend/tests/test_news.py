from __future__ import annotations

from app.services import news
from app.schemas import NewsItem
from app.services.news import clear_news_state, list_news, refresh_live_news, store_live_news


def test_country_news_refresh_uses_profile_query_and_keeps_items_isolated(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        @property
        def text(self) -> str:
            raise RuntimeError("Use GDELT fallback")

        def json(self) -> dict:
            return {
                "articles": [
                    {
                        "url": "https://example.test/solar-auction",
                        "title": "Saudi Arabia solar auction expands",
                        "domain": "example.test",
                        "seendate": "20260817T100000Z",
                    }
                ]
            }

    calls: list[dict[str, object]] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        if "smard" in url:
            raise news.httpx.HTTPError("RSS only covers Germany")
        return FakeResponse()

    clear_news_state()
    monkeypatch.setattr(news.httpx, "get", fake_get)

    result = refresh_live_news("sa", dispatch_notifications=False)

    assert result.status == "live"
    assert "Saudi Arabia" in str(calls[-1]["params"])
    assert len(list_news("sa")) == 1
    assert all(item.url != "https://example.test/solar-auction" for item in list_news("de"))


def test_news_lists_unconfirmed_first_then_confirmed_by_newest_publication_date() -> None:
    clear_news_state()
    try:
        store_live_news([
            NewsItem(id="confirmed-old", title="Older confirmed signal", category="Policy", impact="medium", summary="", why="", source="test", published_at="2026-08-01T00:00:00Z", acknowledged=True, url="https://example.test/confirmed-old"),
        ], "sa")
        store_live_news([
            NewsItem(id="pending-recent", title="Action needed", category="Grid risk", impact="medium", summary="", why="", source="test", published_at="2026-08-14T00:00:00Z", acknowledged=False, url="https://example.test/pending-recent"),
        ], "sa")
        store_live_news([
            NewsItem(id="confirmed-new", title="Latest confirmed signal", category="Demand", impact="medium", summary="", why="", source="test", published_at="2026-08-15T00:00:00Z", acknowledged=True, url="https://example.test/confirmed-new"),
        ], "sa")

        assert [item.id for item in list_news("sa")] == ["pending-recent", "confirmed-new", "confirmed-old"]
    finally:
        clear_news_state()
