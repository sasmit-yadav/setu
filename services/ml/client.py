from __future__ import annotations

from typing import Any

import httpx

from services.api.settings import settings


async def post_ml(path: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any] | None:
    base = settings.hf_space_url.strip()
    if not base:
        return None
    headers: dict[str, str] = {}
    key = settings.internal_ml_key.strip()
    if key:
        headers["X-Internal-Key"] = key
    url = f"{base.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return data if isinstance(data, dict) else None


async def translate_text(
    text: str,
    target_lang: str,
    timeout_s: float,
    model: str,
) -> str | None:
    data = await post_ml(
        "/translate",
        {"text": text, "target_lang": target_lang, "model": model},
        timeout_s,
    )
    if data is None:
        return None
    value = data.get("text") or data.get("translated")
    if not isinstance(value, str) or not value.strip():
        return None
    return value


async def embed_texts(
    texts: list[str],
    timeout_s: float,
    model: str,
) -> list[list[float]] | None:
    data = await post_ml("/embed", {"texts": texts, "model": model}, timeout_s)
    if data is None:
        return None
    vectors = data.get("embeddings")
    if not isinstance(vectors, list):
        return None
    out: list[list[float]] = []
    for item in vectors:
        if not isinstance(item, list):
            return None
        out.append([float(v) for v in item])
    return out
