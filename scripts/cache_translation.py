#!/usr/bin/env python3
"""Write an alert_translation row by hand, and say so in the data.

A Kerala severe/extreme cannot be dispatched without a Malayalam row: the
`translation_exists` quality-gate rule is a hard fail keyed by alert id, so a
freshly composed alert is blocked until the cache holds its state's language.
Normally IndicTrans2 fills that cache. Where the model is not running, this is
the only other way to get past the gate.

`model_id` is left NULL on purpose. That is the field which separates model
output from a human typing a sentence, and nothing here is entitled to claim
the former. A row written by this script is honestly labelled as unattributed,
and `scripts/snapshot.py` still refuses to ship placeholder text.

    # after composing alert 8 on the console
    python scripts/cache_translation.py --alert 8 --lang ml \
        --headline "..." --body "..."

    # reuse an earlier alert's wording verbatim
    python scripts/cache_translation.py --alert 8 --from-alert 7

    # see what an alert already has
    python scripts/cache_translation.py --alert 8 --list

Runs against the DEPLOYED database (.env.cloud), because that is the one the
console and the worker read.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_cloud_env() -> dict[str, str]:
    path = ROOT / ".env.cloud"
    if not path.exists():
        print("Missing .env.cloud - refusing to fall back to .env", file=sys.stderr)
        sys.exit(1)
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value.strip().strip('"').strip("'")
    os.environ.update(env)
    return env


async def show(conn, alert_id: int) -> None:
    alert = await conn.fetchrow(
        "SELECT severity, lifecycle_status, lang, headline FROM alert WHERE id = $1",
        alert_id,
    )
    if alert is None:
        print(f"alert {alert_id} does not exist", file=sys.stderr)
        sys.exit(1)
    print(f"alert {alert_id}: {alert['severity']} / {alert['lifecycle_status']}")
    print(f"  source ({alert['lang']}): {alert['headline']}")
    rows = await conn.fetch(
        "SELECT lang, headline, model_id FROM alert_translation"
        " WHERE alert_id = $1 ORDER BY lang",
        alert_id,
    )
    if not rows:
        print("  no cached translations")
        return
    for row in rows:
        origin = f"model_id={row['model_id']}" if row["model_id"] else "hand-entered"
        print(f"  {row['lang']}: {row['headline']}   [{origin}]")


async def gate(conn, alert_id: int) -> None:
    """Report the one rule this script exists to satisfy."""
    from services.governance.quality_gate import validate

    results = await validate(conn, alert_id)
    for result in results:
        if result.rule_id == "translation_exists":
            mark = "pass" if result.status == "pass" else "FAIL"
            print(f"\ntranslation_exists: {mark}" + (f" - {result.message}" if result.message else ""))


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alert", type=int, required=True, help="target alert id")
    parser.add_argument("--lang", help="ISO code to write, e.g. ml or hi")
    parser.add_argument("--headline")
    parser.add_argument("--body")
    parser.add_argument(
        "--from-alert",
        type=int,
        help="copy every non-source translation from this alert instead",
    )
    parser.add_argument("--list", action="store_true", help="show what exists and exit")
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    env = load_cloud_env()
    import asyncpg

    conn = await asyncpg.connect(env["DATABASE_URL_DIRECT"])
    try:
        if args.list:
            await show(conn, args.alert)
            await gate(conn, args.alert)
            return 0

        if args.from_alert:
            source_lang = await conn.fetchval(
                "SELECT lang FROM alert WHERE id = $1", args.from_alert
            )
            rows = await conn.fetch(
                "SELECT lang, headline, body FROM alert_translation"
                " WHERE alert_id = $1 AND lang <> $2",
                args.from_alert,
                source_lang or "",
            )
            if not rows:
                print(f"alert {args.from_alert} has no translations to copy", file=sys.stderr)
                return 1
            print(f"copying {len(rows)} row(s) from alert {args.from_alert}:")
            for row in rows:
                print(f"  {row['lang']}: {row['headline']}")
            print(
                "\n  NOTE: this is a different alert's wording. Only do this when the\n"
                "  new alert says the same thing, or the cache will disagree with the\n"
                "  headline an officer actually wrote."
            )
            if args.dry_run:
                print("\ndry run - nothing written")
                return 0
            async with conn.transaction():
                for row in rows:
                    await conn.execute(
                        """
                        INSERT INTO alert_translation (alert_id, lang, headline, body, model_id)
                        VALUES ($1, $2, $3, $4, NULL)
                        ON CONFLICT (alert_id, lang)
                        DO UPDATE SET headline = EXCLUDED.headline, body = EXCLUDED.body
                        """,
                        args.alert,
                        row["lang"],
                        row["headline"],
                        row["body"],
                    )
        else:
            if not (args.lang and args.headline and args.body):
                parser.error("give --lang with --headline and --body, or use --from-alert")
            print(f"alert {args.alert}  {args.lang}")
            print(f"  headline: {args.headline}")
            print(f"  body    : {args.body}")
            print("  model_id: NULL (hand-entered, not model output)")
            if args.dry_run:
                print("\ndry run - nothing written")
                return 0
            await conn.execute(
                """
                INSERT INTO alert_translation (alert_id, lang, headline, body, model_id)
                VALUES ($1, $2, $3, $4, NULL)
                ON CONFLICT (alert_id, lang)
                DO UPDATE SET headline = EXCLUDED.headline, body = EXCLUDED.body
                """,
                args.alert,
                args.lang,
                args.headline,
                args.body,
            )

        print()
        await show(conn, args.alert)
        await gate(conn, args.alert)
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
