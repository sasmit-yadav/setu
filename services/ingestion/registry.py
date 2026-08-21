from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any

import asyncpg

from services.ingestion.adapters.base import AlertSourceAdapter

logger = logging.getLogger(__name__)


def import_adapter(class_path: str, config: dict[str, Any]) -> AlertSourceAdapter:
    module_name, _, class_name = class_path.rpartition(".")
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    # Only pass what the adapter's __init__ actually accepts. Shared HTTP
    # policy (below) is injected for every adapter, but not every adapter
    # takes every key — passing them blindly would TypeError on the ones
    # that don't.
    accepted = inspect.signature(cls).parameters
    kwargs = {k: v for k, v in config.items() if k in accepted}
    return cls(**kwargs)


async def load_adapters(conn: asyncpg.Connection) -> dict[str, AlertSourceAdapter]:
    """Build the adapter registry from the alert_source table (Rule 2/Rule 3:
    adding a source is one INSERT, never a code change).

    Shared HTTP policy — request timeout and the not-modified status code —
    lives in app_config rather than being duplicated into every source's
    config JSON, because it is a system-wide decision, not a per-feed one.
    The registry injects it here. Without this the adapters raised
    "missing 2 required positional arguments: 'timeout_s' and
    'not_modified_status'" against the real seeded rows, while fixture-based
    unit tests (which construct adapters directly) passed.
    """
    http_defaults = {
        "timeout_s": int(
            await conn.fetchval(
                "SELECT value::int FROM app_config WHERE key = 'ingest.http_timeout_s'"
            )
        ),
        "not_modified_status": int(
            await conn.fetchval(
                "SELECT value::int FROM app_config WHERE key = 'ingest.http_not_modified_status'"
            )
        ),
    }

    registry: dict[str, AlertSourceAdapter] = {}
    rows = await conn.fetch(
        """
        SELECT source_id, class_path, config, is_authoritative, enabled
        FROM alert_source
        WHERE enabled
        """
    )
    for row in rows:
        config = dict(row["config"])
        try:
            adapter = import_adapter(row["class_path"], {**http_defaults, **config, "conn": conn})
        except (ImportError, AttributeError, TypeError) as exc:
            # One unbuildable adapter must never take the whole registry down
            # with it. A seeded row whose module does not exist yet (or whose
            # __init__ signature drifted from its config) is a real problem,
            # but it is THAT source's problem — USGS should still poll while
            # the thunderstorm nowcast is unwritten. Logged loudly, never
            # silently swallowed: an adapter that vanishes from the registry
            # without a word is how a feed stops ingesting unnoticed.
            logger.error(
                "adapter_unavailable source_id=%s class_path=%s error=%s: %s",
                row["source_id"],
                row["class_path"],
                type(exc).__name__,
                exc,
            )
            continue
        adapter.source_id = row["source_id"]
        adapter.is_authoritative = row["is_authoritative"]
        registry[row["source_id"]] = adapter
    return registry
