from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.api.db import connect_direct
from services.ingestion.poller import poll_source


async def _poll_usgs() -> None:
    async with connect_direct() as conn, conn.transaction():
        await poll_source(conn, "usgs")


async def _poll_gdacs() -> None:
    async with connect_direct() as conn, conn.transaction():
        await poll_source(conn, "gdacs")


def main() -> None:
    async def run() -> None:
        scheduler = AsyncIOScheduler(timezone=UTC)
        scheduler.add_job(_poll_usgs, "interval", minutes=5, next_run_time=datetime.now(UTC))
        scheduler.add_job(_poll_gdacs, "interval", minutes=5, next_run_time=datetime.now(UTC))
        scheduler.start()
        await asyncio.Event().wait()

    asyncio.run(run())


if __name__ == "__main__":
    main()
