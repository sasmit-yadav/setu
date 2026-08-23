#!/usr/bin/env python3
"""One command that answers "is the demo going to work right now".

Every check reads. Nothing here dispatches, sends, approves or writes, so it
is safe to run repeatedly — including while an audience is watching. It talks
to the DEPLOYED stack via .env.cloud, because that is what the demo uses; a
green local run has never been the question.

    python scripts/preflight_demo.py
    python scripts/preflight_demo.py --alert 8

Exit code is 1 if any check fails, so it can gate a rehearsal.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Importable when run as `python scripts/preflight_demo.py` from anywhere.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEMO_UNIT = 8157
SIREN_HEALTH_URL = "http://127.0.0.1:9099/"
OFFICERS = ("officer.a@setu.example", "officer.b@setu.example")
REQUIRED_ENV = (
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "FCM_SERVICE_ACCOUNT_JSON",
    "PGCRYPTO_SYM_KEY",
    "PHONE_HASH_PEPPER",
)
COLD_START_S = 5.0

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
_results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    _results.append((status, name, detail))
    mark = {PASS: "  ok  ", FAIL: " FAIL ", WARN: " warn "}[status]
    print(f"[{mark}] {name}" + (f" - {detail}" if detail else ""), flush=True)


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


def demo_password() -> str | None:
    """The demo password lives in .env, not .env.cloud - it is a local secret."""
    if os.environ.get("SETU_DEMO_PASSWORD"):
        return os.environ["SETU_DEMO_PASSWORD"]
    path = ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SETU_DEMO_PASSWORD="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


async def check_http(env: dict[str, str], alert_id: int) -> None:
    import httpx

    api = env.get("PUBLIC_BASE_URL", "").rstrip("/")
    password = demo_password()

    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        try:
            response = await client.get(f"{api}/health")
            seconds = response.elapsed.total_seconds()
            note = " (cold start - hit it again before anyone sits down)"
            suffix = note if seconds > COLD_START_S else ""
            record(
                PASS if response.status_code == 200 else FAIL,
                "API /health",
                f"{response.status_code} in {seconds:.2f}s{suffix}",
            )
        except Exception as exc:
            record(FAIL, "API /health", repr(exc))
            return

        for name, url in (
            ("citizen PWA", "https://setucitizen.vercel.app"),
            ("officer console", "https://setuconsole.vercel.app"),
        ):
            try:
                r = await client.get(url)
                record(PASS if r.status_code == 200 else FAIL, name, str(r.status_code))
            except Exception as exc:
                record(FAIL, name, repr(exc))

        try:
            r = await client.get(f"{api}/api/v1/public/signing-key")
            ok = r.status_code == 200 and bool(r.json())
            record(PASS if ok else FAIL, "signing key published", str(r.status_code))
        except Exception as exc:
            record(FAIL, "signing key published", repr(exc))

        tokens: dict[str, str] = {}
        for email in OFFICERS:
            if not password:
                record(WARN, f"login {email}", "SETU_DEMO_PASSWORD not found")
                continue
            try:
                r = await client.post(
                    f"{api}/api/v1/auth/login",
                    json={"email": email, "password": password},
                )
                if r.status_code != 200:
                    record(FAIL, f"login {email}", str(r.status_code))
                    continue
                tokens[email] = r.json()["access_token"]
                me = await client.get(
                    f"{api}/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {tokens[email]}"},
                )
                scope = me.json().get("unit_scope_id") if me.status_code == 200 else None
                record(PASS if scope else FAIL, f"login {email}", f"unit_scope_id={scope}")
            except Exception as exc:
                record(FAIL, f"login {email}", repr(exc))

        token = tokens.get(OFFICERS[0])
        if token:
            try:
                r = await client.post(
                    f"{api}/api/v1/alerts/{alert_id}/validate",
                    headers={"Authorization": f"Bearer {token}"},
                )
                body = r.json()
                blocked = bool(body.get("blocked", True))
                bad = [
                    x["rule_id"]
                    for x in body.get("results", [])
                    if x.get("status") == "fail"
                ]
                record(
                    FAIL if blocked else PASS,
                    f"quality gate alert {alert_id}",
                    "blocked by " + ", ".join(bad) if blocked else "all rules pass",
                )
            except Exception as exc:
                record(FAIL, f"quality gate alert {alert_id}", repr(exc))

        try:
            r = await client.get(SIREN_HEALTH_URL, timeout=3)
            record(PASS if r.status_code == 200 else WARN, "siren listener", str(r.status_code))
        except Exception:
            record(WARN, "siren listener", "not running - scripts/siren_listener.py")


async def check_db(env: dict[str, str], alert_id: int) -> None:
    import asyncpg

    conn = await asyncpg.connect(env["DATABASE_URL_DIRECT"])
    try:
        alert = await conn.fetchrow(
            """
            SELECT severity, lifecycle_status, lang, (expires_at > now()) AS live
            FROM alert WHERE id = $1
            """,
            alert_id,
        )
        if alert is None:
            record(FAIL, f"alert {alert_id}", "does not exist")
        else:
            record(
                PASS if alert["lifecycle_status"] == "draft" else WARN,
                f"alert {alert_id}",
                f"{alert['severity']} / {alert['lifecycle_status']} / source {alert['lang']}",
            )
            record(
                PASS if alert["live"] else FAIL,
                f"alert {alert_id} not expired",
                "expiry in the future" if alert["live"] else "ALREADY EXPIRED",
            )

        rows = await conn.fetch(
            "SELECT lang, model_id FROM alert_translation WHERE alert_id = $1 ORDER BY lang",
            alert_id,
        )
        have = sorted(r["lang"] for r in rows)
        with_model = sum(1 for r in rows if r["model_id"] is not None)
        record(
            PASS if "ml" in have else FAIL,
            f"alert {alert_id} translations",
            f"{have} - {with_model} carry a model_id",
        )

        recipients = await conn.fetch(
            """
            SELECT id, kind, preferred_lang,
                   (push_token IS NOT NULL) AS token,
                   (phone_enc IS NOT NULL) AS phone
            FROM recipient
            WHERE unit_id = $1 AND consented_at IS NOT NULL AND opted_out_at IS NULL
            ORDER BY id
            """,
            DEMO_UNIT,
        )
        devices = (await conn.fetchval(
            "SELECT value FROM app_config WHERE key = 'recipient.device_kinds'"
        ) or "").split(",")
        people = [r for r in recipients if r["kind"] not in devices]
        record(
            PASS if people else FAIL,
            f"people we can warn in {DEMO_UNIT}",
            f"{len(people)} people + {len(recipients) - len(people)} village device(s)",
        )
        for r in recipients:
            record(
                PASS,
                f"  recipient {r['id']} ({r['kind']})",
                f"lang={r['preferred_lang']} "
                f"push={'y' if r['token'] else 'n'} "
                f"phone={'y' if r['phone'] else 'n'}",
            )
        if recipients and not any(r["token"] for r in recipients):
            record(FAIL, "a live push token", "tap Enable alerts on the presenting phone")

        raw = await conn.fetchval("SELECT config FROM channel WHERE code = 'siren'")
        cfg = json.loads(raw) if isinstance(raw, str) else (raw or {})
        record(
            PASS if cfg.get("webhook_url") else WARN,
            "siren webhook configured",
            cfg.get("webhook_url") or "empty - siren falls back to simulated",
        )

        nodes = await conn.fetchval(
            "SELECT count(*) FROM relay_node WHERE unit_id = $1 AND active",
            DEMO_UNIT,
        )
        record(PASS if nodes else WARN, "active relay nodes", str(nodes))

        # "In India" is intersecting an admin_unit we could actually target -
        # the same predicate the targeting engine uses. A lat/lon rectangle
        # around India also contains Kabul and Kathmandu, so counting by bbox
        # reports foreign earthquakes as domestic.
        for source in ("usgs", "gdacs"):
            total = await conn.fetchval(
                "SELECT count(*) FROM alert WHERE source_id = $1 AND lifecycle_status = 'draft'",
                source,
            )
            domestic = await conn.fetchval(
                """
                SELECT count(*) FROM alert a
                WHERE a.source_id = $1 AND a.lifecycle_status = 'draft'
                  AND EXISTS (
                    SELECT 1 FROM admin_unit u WHERE ST_Intersects(u.geom, a.area)
                  )
                """,
                source,
            )
            record(
                PASS if total else WARN,
                f"{source} live drafts",
                f"{total} worldwide, {domestic} on Indian soil",
            )
        nowcast = await conn.fetchval(
            "SELECT count(*) FROM alert WHERE source_id = 'thunderstorm_nowcast'"
            " AND lifecycle_status = 'draft'"
        )
        record(PASS, "our nowcast drafts", f"{nowcast} (our model - never authoritative)")

        for name in REQUIRED_ENV:
            record(
                PASS if env.get(name) else FAIL,
                f"env {name}",
                "set" if env.get(name) else "MISSING",
            )
        seed = env.get("ALERT_SIGNING_SEED_B64") or env.get("ALERT_SIGNING_SEED_B")
        record(PASS if seed else FAIL, "env ALERT_SIGNING_SEED_B64",
               "set" if seed else "MISSING - deliveries will not be signed")
    finally:
        await conn.close()


async def check_redis(env: dict[str, str]) -> None:
    from redis.asyncio import Redis

    from services.delivery.keys import RedisKeys

    keys = RedisKeys(env.get("REDIS_NAMESPACE"))
    redis = Redis.from_url(env["REDIS_URL"], decode_responses=True)
    try:
        await redis.ping()
        record(PASS, "Upstash reachable")
        # redis-py's xinfo_groups() assumes a map reply and raises AttributeError
        # against Upstash, which answers with a flat list. That looked exactly
        # like "no consumer group" and reported a running worker as absent, so
        # issue the raw command and pair the fields ourselves.
        groups: list[dict[str, object]] = []
        try:
            raw = await redis.execute_command("XINFO", "GROUPS", keys.stream_delivery())
            for entry in raw or []:
                if isinstance(entry, dict):
                    groups.append(entry)
                elif isinstance(entry, (list, tuple)):
                    pairs = list(entry)
                    groups.append(dict(zip(pairs[::2], pairs[1::2], strict=False)))
        except Exception as exc:
            record(WARN, "worker consumer group", f"could not read: {exc!r}")
        if not groups:
            record(WARN, "worker consumer group", "not created yet - appears on first dispatch")
        for group in groups:
            consumers = int(group.get("consumers", 0) or 0)
            pending = int(group.get("pending", 0) or 0)
            detail = f"{consumers} consumer(s), {pending} pending"
            if not consumers:
                detail += " - start run.py worker-cloud"
            record(PASS if consumers else FAIL, "worker consuming", detail)
            if pending:
                record(
                    WARN,
                    "unacked messages on the stream",
                    f"{pending} - a past dispatch was never acked; harmless but not clean",
                )
    except Exception as exc:
        record(FAIL, "Upstash reachable", repr(exc))
    finally:
        await redis.aclose()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alert", type=int, default=7, help="draft alert to validate")
    args = parser.parse_args()

    env = load_cloud_env()
    print(f"preflight against the deployed stack (alert {args.alert})\n", flush=True)
    await check_http(env, args.alert)
    await check_db(env, args.alert)
    await check_redis(env)

    failed = [r for r in _results if r[0] == FAIL]
    warned = [r for r in _results if r[0] == WARN]
    ok = len(_results) - len(failed) - len(warned)
    print(f"\n{ok} ok, {len(warned)} warn, {len(failed)} FAIL", flush=True)
    if failed:
        print("\nfix before presenting:", flush=True)
        for _, name, detail in failed:
            print(f"  - {name}: {detail}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
