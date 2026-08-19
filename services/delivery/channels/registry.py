from __future__ import annotations

import importlib

import asyncpg

from services.delivery.channels.base import ChannelAdapter


async def load_channel_adapters(conn: asyncpg.Connection) -> dict[str, ChannelAdapter]:
    registry: dict[str, ChannelAdapter] = {}
    rows = await conn.fetch(
        "SELECT code, class_path, config FROM channel WHERE enabled ORDER BY id"
    )
    for row in rows:
        module_name, _, class_name = row["class_path"].rpartition(".")
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        config = dict(row["config"] or {})
        registry[row["code"]] = cls(conn, config)
    return registry


def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
