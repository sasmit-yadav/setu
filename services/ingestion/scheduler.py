from __future__ import annotations

import argparse
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


async def _poll_thunderstorm() -> None:
    try:
        async with connect_direct() as conn, conn.transaction():
            await poll_source(conn, "thunderstorm_nowcast")
    except KeyError:
        # Seeded disabled, or the adapter failed to import — USGS/GDACS still run.
        return


async def poll_once() -> None:
    """One pass over every enabled source, then return.

    The demo needs the draft inbox populated before anyone sits down, not a
    daemon holding a terminal. Each poller is independent: GDACS failing must
    not stop USGS from landing its rows, so they are awaited separately and a
    failure is reported rather than raised.
    """
    for label, poll in (
        ("usgs", _poll_usgs),
        ("gdacs", _poll_gdacs),
        ("thunderstorm_nowcast", _poll_thunderstorm),
    ):
        try:
            await poll()
            print(f"  polled {label}", flush=True)
        except Exception as exc:  # noqa: BLE001 - one bad source must not stop the rest
            print(f"  {label} FAILED: {exc!r}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="SETU ingestion")
    parser.add_argument(
        "--once",
        action="store_true",
        help="poll every enabled source once and exit, instead of scheduling",
    )
    args = parser.parse_args()

    if args.once:
        asyncio.run(poll_once())
        return

    async def run() -> None:
        scheduler = AsyncIOScheduler(timezone=UTC)
        scheduler.add_job(_poll_usgs, "interval", minutes=5, next_run_time=datetime.now(UTC))
        scheduler.add_job(_poll_gdacs, "interval", minutes=5, next_run_time=datetime.now(UTC))
        scheduler.add_job(
            _poll_thunderstorm, "interval", minutes=15, next_run_time=datetime.now(UTC)
        )
        scheduler.start()
        await asyncio.Event().wait()

    asyncio.run(run())


if __name__ == "__main__":
    main()
