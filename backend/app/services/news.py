from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any
from xml.etree import ElementTree

import httpx
from sqlalchemy import delete, select

from ..data import NEWS_ITEMS
from ..db import NewsRecord, session_scope
from ..schemas import AcknowledgeResult, NewsItem, NewsRefreshResult
from .notifications import dispatch_for_news
from .countries import get_country_profile
from .event_extraction import extract_event_fields
from .feature_store import save_evidence


GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = '("Germany" OR "German") (solar OR photovoltaic OR PV)'
SMARD_RSS_URL = "https://www.smard.de/service/rss/en/feed.rss"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def scoped_url(profile_id: str, url: str | None) -> str | None:
    return f"{profile_id}::{url}" if url else None


def raw_url(value: str | None) -> str | None:
    return value.split("::", 1)[1] if value and "::" in value else value


def published_sort_timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return parsedate_to_datetime(value).timestamp()
        except (TypeError, ValueError):
            return float("-inf")


def order_news_for_review(items: list[NewsItem]) -> list[NewsItem]:
    """Put open review work first; keep the confirmed audit trail newest-first."""
    return sorted(
        items,
        key=lambda item: (item.acknowledged, -published_sort_timestamp(item.published_at)),
    )


def record_to_news_item(record: NewsRecord) -> NewsItem:
    profile_id = (record.url or "de::").split("::", 1)[0]
    return NewsItem(
        id=record.id.removeprefix(f"{profile_id}-"),
        title=record.title,
        category=record.category,
        impact=record.impact,
        summary=record.summary,
        why=record.why,
        source=record.source,
        published_at=record.published_at,
        acknowledged=record.acknowledged,
        url=raw_url(record.url),
    )


def store_live_news(candidates: list[NewsItem], profile_id: str = "de") -> list[NewsItem]:
    stored: list[NewsItem] = []
    with session_scope() as session:
        existing_ids = set(session.scalars(select(NewsRecord.id)).all())
        existing_urls = {url for url in session.scalars(select(NewsRecord.url)).all() if url}
        for item in candidates:
            scoped_id = f"{profile_id}-{item.id}"
            stored_url = scoped_url(profile_id, item.url)
            if scoped_id in existing_ids or (stored_url and stored_url in existing_urls):
                continue
            session.add(
                NewsRecord(
                    id=scoped_id,
                    title=item.title,
                    category=item.category,
                    impact=item.impact,
                    summary=item.summary,
                    why=item.why,
                    source=item.source,
                    published_at=item.published_at,
                    acknowledged=item.acknowledged,
                    url=stored_url,
                    created_at=now_iso(),
                )
            )
            existing_ids.add(scoped_id)
            if stored_url:
                existing_urls.add(stored_url)
            stored.append(item)
    if stored:
        from ..schemas import EvidenceItemInput

        save_evidence(
            profile_id,
            [
                EvidenceItemInput(
                    title=item.title,
                    source=item.source,
                    url=item.url,
                    summary=item.summary,
                    excerpt=f"{item.summary} {item.why}".strip()[:1200],
                    published_at=item.published_at,
                    category=item.category,
                    event_type=event.event_type,
                    impact_direction=event.impact_direction,
                    impact_factors=event.impact_factors,
                    confidence=event.confidence,
                    extraction_mode=event.extraction_mode,
                )
                for item in stored
                for event in [extract_event_fields(item.title, item.summary)]
            ],
        )
    return stored


def classify_article(title: str) -> tuple[str, str, str]:
    normalized = title.lower()
    if any(word in normalized for word in ("subsidy", "policy", "regulation", "tariff", "permit", "law")):
        return "Policy", "high", "政策或支持机制变化可能影响项目经济性，需要与正式文件交叉核验。"
    if any(word in normalized for word in ("grid", "connection", "network", "curtailment")):
        return "Grid risk", "medium", "并网与电网约束可能影响项目交付节奏。"
    if any(word in normalized for word in ("demand", "auction", "capacity", "installation", "deployment")):
        return "Demand", "medium", "需求或新增部署信号可能影响市场增长假设。"
    return "Market monitor", "low", "该动态与当前市场监测主题相关，但不应单独改变市场判断。"


def parse_gdelt_articles(payload: dict[str, Any], profile_id: str = "de") -> list[NewsItem]:
    seen_urls: set[str] = set()
    parsed: list[NewsItem] = []
    for article in payload.get("articles", []):
        url = str(article.get("url", "")).strip()
        title = str(article.get("title", "")).strip()
        if not url or not title or url in seen_urls:
            continue
        seen_urls.add(url)
        category, impact, why = classify_article(title)
        digest = sha256(url.encode("utf-8")).hexdigest()[:10]
        parsed.append(
            NewsItem(
                id=f"G-{profile_id}-{digest}",
                title=title,
                category=category,
                impact=impact,
                summary="来自配置化公开新闻检索源的实时信号；在改变评分或决策前必须由分析师核验原文。",
                why=why,
                source=str(article.get("domain") or "GDELT"),
                published_at=str(article.get("seendate") or ""),
                acknowledged=False,
                url=url,
            )
        )
    return parsed


def parse_rss_articles(xml_text: str, source: str, profile_id: str = "de") -> list[NewsItem]:
    root = ElementTree.fromstring(xml_text)
    seen_urls: set[str] = set()
    parsed: list[NewsItem] = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        url = (node.findtext("link") or "").strip()
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        category, impact, why = classify_article(title)
        digest = sha256(url.encode("utf-8")).hexdigest()[:10]
        parsed.append(
            NewsItem(
                id=f"R-{profile_id}-{digest}",
                title=title,
                category=category,
                impact=impact,
                summary="来自配置化公开 RSS 的行业信号；在改变评分或决策前必须由分析师核验原文。",
                why=why,
                source=source,
                published_at=(node.findtext("pubDate") or "").strip(),
                acknowledged=False,
                url=url,
            )
        )
    return parsed


def list_news(profile_id: str = "de") -> list[NewsItem]:
    with session_scope() as session:
        persisted = session.scalars(select(NewsRecord).order_by(NewsRecord.created_at.desc())).all()
    prefix = f"{profile_id}::"
    selected = [record_to_news_item(record) for record in persisted if (record.url or "").startswith(prefix)]
    seeded = [NewsItem(**item) for item in NEWS_ITEMS] if profile_id == "de" else []
    return order_news_for_review(selected + seeded)


def clear_news_state() -> None:
    with session_scope() as session:
        session.execute(delete(NewsRecord))


def refresh_live_news(profile_id: str = "de", dispatch_notifications: bool = True) -> NewsRefreshResult:
    profile = get_country_profile(profile_id)
    if profile is None:
        raise ValueError("Country profile not found")
    if profile_id == "de":
        try:
            rss_response = httpx.get(SMARD_RSS_URL, timeout=20, follow_redirects=True)
            rss_response.raise_for_status()
            candidates = parse_rss_articles(rss_response.text, "SMARD", profile_id)
            additions = store_live_news(candidates, profile_id)
            deliveries = dispatch_for_news(additions) if dispatch_notifications else []
            return NewsRefreshResult(
                status="live",
                added=len(additions),
                message=f"已从官方配置的 RSS 刷新 {len(additions)} 条待人工核验的市场动态。",
                notifications_previewed=sum(item.mode == "preview" for item in deliveries),
                notifications_sent=sum(item.mode == "sent" for item in deliveries),
            )
        except (httpx.HTTPError, ValueError, ElementTree.ParseError):
            pass
    try:
        response = httpx.get(
            GDELT_ENDPOINT,
            params={"query": profile.news_query, "mode": "artlist", "format": "json", "maxrecords": 10, "timespan": "7d"},
            timeout=25,
        )
        response.raise_for_status()
        candidates = parse_gdelt_articles(response.json(), profile_id)
        additions = store_live_news(candidates, profile_id)
        deliveries = dispatch_for_news(additions) if dispatch_notifications else []
        return NewsRefreshResult(
            status="live",
            added=len(additions),
            message=f"已检索公开新闻信号，新增 {len(additions)} 条待人工核验的动态。",
            notifications_previewed=sum(item.mode == "preview" for item in deliveries),
            notifications_sent=sum(item.mode == "sent" for item in deliveries),
        )
    except (httpx.HTTPError, ValueError) as error:
        return NewsRefreshResult(
            status="degraded",
            added=0,
            message=f"新闻源暂时不可用，保留已有动态：{error}",
        )


def acknowledge(news_id: str) -> AcknowledgeResult | None:
    for item in NEWS_ITEMS:
        if item["id"] == news_id:
            item["acknowledged"] = True
            return AcknowledgeResult(id=news_id, acknowledged=True)
    with session_scope() as session:
        record = session.get(NewsRecord, news_id)
        if record is None:
            record = session.scalar(select(NewsRecord).where(NewsRecord.id.like(f"%-{news_id}")))
        if record is not None:
            record.acknowledged = True
            return AcknowledgeResult(id=news_id, acknowledged=True)
    return None
