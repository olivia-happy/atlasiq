from __future__ import annotations

import os

from ..schemas import NewsPollingStatus


DEFAULT_NEWS_POLL_INTERVAL_SECONDS = 300


def news_poll_interval_seconds() -> int:
    raw_value = os.getenv("NEWS_POLL_INTERVAL_SECONDS")
    if raw_value is None:
        return DEFAULT_NEWS_POLL_INTERVAL_SECONDS
    try:
        return max(0, int(raw_value))
    except ValueError:
        return DEFAULT_NEWS_POLL_INTERVAL_SECONDS


def get_news_polling_status() -> NewsPollingStatus:
    interval_seconds = news_poll_interval_seconds()
    return NewsPollingStatus(enabled=interval_seconds > 0, interval_seconds=interval_seconds)
