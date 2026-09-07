from __future__ import annotations

import json
import os
from typing import Any


def redis_client():
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2)
        client.ping()
        return client
    except Exception:
        return None


def get_json(key: str) -> dict[str, Any] | None:
    client = redis_client()
    if client is None:
        return None
    raw = client.get(key)
    return json.loads(raw) if raw else None


def set_json(key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    client = redis_client()
    if client is not None:
        client.setex(key, ttl_seconds, json.dumps(value, ensure_ascii=False))
