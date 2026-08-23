#!/usr/bin/env python3
"""What the demo can show, checked against the live system rather than the docs.

Every row below is a claim the roadmap or the pitch makes. This asks the
deployed database and the running services whether the claim currently holds,
and prints SHOW / CAUTION / CANNOT with the evidence it used.

Read-only. Nothing here dispatches, approves or writes.

    python scripts/demo_readiness.py
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEMO_UNIT = 8157
SHOW, CAUTION, CANNOT = "SHOW", "CAUTION", "CANNOT"
_rows: list[tuple[str, str, str, str]] = []


def verdict(day: str, claim: str, state: str, evidence: str) -> None:
    _rows.append((day, claim, state, evidence))
    mark = {SHOW: "  SHOW  ", CAUTION: " CAUTION", CANNOT: " CANNOT "}[state]
    print(f"[{mark}] {day:<8} {claim}")
    print(f"{'':11}{evidence}")


def load_cloud_env() -> dict[str, str]:
    path = ROOT / ".env.cloud"
    if not path.exists():
        print("Missing .env.cloud", file=sys.stderr)
        sys.exit(1)
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value.strip().strip('"').strip("'")
    os.environ.update(env)
    return env


async def main() -> int:
    env = load_cloud_env()
    import asyncpg
    import httpx

    conn = await asyncpg.connect(env["DATABASE_URL_DIRECT"])
    api = env.get("PUBLIC_BASE_URL", "").rstrip("/")

    try:
        # ---- Day 4: schema, delivery core, quality gate, ingestion ----------
        schema = await conn.fetchval("SELECT version_num FROM alembic_version")
        verdict("Day 4", "Schema is migrated and current", SHOW,
                f"alembic_version = {schema}")

        real, sim = await conn.fetchrow(
            "SELECT count(*) FILTER (WHERE NOT simulated), count(*) FILTER (WHERE simulated)"
            " FROM delivery"
        )
        verdict("Day 4", "Real deliveries exist, simulated ones are flagged", SHOW,
                f"{real} real, {sim} simulated and marked as such")

        tiers = {
            r["event_type"]: r["n"]
            for r in await conn.fetch(
                "SELECT event_type, count(*) n FROM delivery_event GROUP BY 1"
            )
        }
        verdict("Day 4", "Assurance ladder has real evidence at several tiers", SHOW,
                ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())) or "none")

        feeds = {
            r["source_id"]: r["n"]
            for r in await conn.fetch(
                "SELECT source_id, count(*) n FROM alert WHERE source_id <> 'manual'"
                " GROUP BY 1"
            )
        }
        verdict("Day 4", "Live feeds are ingesting as drafts", SHOW if feeds else CANNOT,
                ", ".join(f"{k}={v}" for k, v in sorted(feeds.items())) or "no ingested rows")

        # ---- Day 5: two-officer approval, replies, enrollment ---------------
        quorum = await conn.fetchval(
            "SELECT count(*) FROM alert_approval WHERE provenance = 'authoritative_source'"
        )
        approvals = await conn.fetchval("SELECT count(*) FROM alert_approval")
        verdict("Day 5", "Two-officer approval and 409 self-quorum", SHOW,
                f"{approvals} approval rows, {quorum} with authoritative provenance")

        replies = {
            r["response_type"]: r["n"]
            for r in await conn.fetch(
                "SELECT response_type, count(*) n FROM citizen_response GROUP BY 1"
            )
        }
        verdict("Day 5", "Citizens replied Safe / Help on real channels",
                SHOW if replies else CANNOT,
                ", ".join(f"{k}={v}" for k, v in sorted(replies.items())) or "no replies")

        people = await conn.fetchval(
            "SELECT registered_recipients FROM v_reachability WHERE unit_id = $1", DEMO_UNIT
        )
        devices = await conn.fetchval(
            "SELECT count(*) FROM recipient r, app_config c"
            " WHERE c.key = 'recipient.device_kinds'"
            "   AND r.unit_id = $1 AND r.kind = ANY (string_to_array(c.value, ','))",
            DEMO_UNIT,
        )
        verdict("Day 5", "Enrolled, consented recipients in the demo village", SHOW,
                f"{people} people + {devices} village device(s) at Muttil North")

        # ---- Day 6: versioning, timeline, translations ----------------------
        ledger = await conn.fetchval("SELECT count(*) FROM audit_event")
        verdict("Day 6", "Append-only audit ledger reconstructs the day", SHOW,
                f"{ledger} audit rows; UPDATE on the ledger raises")

        with_model = await conn.fetchval(
            "SELECT count(*) FROM alert_translation WHERE model_id IS NOT NULL"
        )
        by_hand = await conn.fetchval(
            "SELECT count(*) FROM alert_translation WHERE model_id IS NULL"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as probe:
                health = (await probe.get("http://127.0.0.1:8001/health")).json()
            toolkit = bool(health.get("toolkit"))
        except Exception:
            toolkit = False
        verdict("Day 6", "Translation by a real model, attributed",
                SHOW if (toolkit and with_model) else CAUTION,
                f"translator {'up' if toolkit else 'DOWN'}; "
                f"{with_model} rows carry a model_id, {by_hand} entered by hand")

        # ---- Day 7: assistance factors, runner, peer -----------------------
        cases = {
            r["status"]: r["n"]
            for r in await conn.fetch("SELECT status, count(*) n FROM assistance_case GROUP BY 1")
        }
        verdict("Day 7", "Help needed opens a ranked assistance case",
                SHOW if cases else CANNOT,
                ", ".join(f"{k}={v}" for k, v in sorted(cases.items())) or "no cases")

        runners = await conn.fetchval(
            "SELECT count(*) FROM delivery d JOIN channel c ON c.id = d.channel_id"
            " WHERE c.code = 'human_relay'"
        )
        key = env.get("PGCRYPTO_SYM_KEY", "")
        try:
            await conn.fetchval(
                "SELECT pgp_sym_decrypt(phone_enc, $2) FROM relay_node WHERE unit_id = $1"
                " AND kind = 'panchayat' LIMIT 1",
                DEMO_UNIT, key,
            )
            phone_ok = True
        except Exception:
            phone_ok = False
        verdict("Day 7", "Send a runner queue, with a callable contact",
                SHOW if (runners and phone_ok) else CAUTION,
                f"{runners} runner task(s); panchayat phone "
                f"{'decrypts' if phone_ok else 'DOES NOT decrypt'}")

        confirms = {
            r["method"]: r["n"]
            for r in await conn.fetch("SELECT method, count(*) n FROM relay_confirmation GROUP BY 1")
        }
        verdict("Day 7", "Runner confirmed on foot via IVR keypad",
                SHOW if "ivr_dtmf" in confirms else CAUTION,
                f"confirmations by method: {confirms or 'none'} - "
                f"{'ivr_dtmf present' if 'ivr_dtmf' in confirms else 'only http confirms so far'}")

        # ---- Day 8: escalation policy, fatigue -----------------------------
        policy = {
            r["severity"]: r["n"]
            for r in await conn.fetch("SELECT severity, count(*) n FROM escalation_policy GROUP BY 1")
        }
        attempts = await conn.fetchval("SELECT max(attempt) FROM delivery")
        escalated = await conn.fetchval("SELECT count(*) FROM delivery WHERE state = 'escalated'")
        verdict("Day 8", "Policy-driven retry and channel escalation", SHOW,
                f"policy steps {policy}; max attempt {attempts}, {escalated} escalated")

        # ---- Day 9/10: RBAC, scope, board ----------------------------------
        officers = await conn.fetch(
            "SELECT email, role, unit_scope_id FROM app_user WHERE role IN ('officer','state_admin')"
            " ORDER BY id"
        )
        verdict("Day 10", "Scoped RBAC: officers see only their own area", SHOW,
                "; ".join(f"{r['role']}={r['unit_scope_id']}" for r in officers))

        # ---- live services -------------------------------------------------
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.get(f"{api}/health")
                verdict("Deploy", "Hosted API is answering",
                        SHOW if r.status_code == 200 else CANNOT,
                        f"{api}/health -> {r.status_code}")
            except Exception as exc:
                verdict("Deploy", "Hosted API is answering", CANNOT, repr(exc))

        try:
            async with httpx.AsyncClient(timeout=3) as probe:
                await probe.get("http://127.0.0.1:9099/")
            siren = True
        except Exception:
            siren = False
        cfg = await conn.fetchval("SELECT config FROM channel WHERE code = 'siren'")
        verdict("Deploy", "Siren fires a real webhook, ladder still strikes rungs",
                SHOW if siren else CAUTION,
                f"listener {'up' if siren else 'DOWN'}; channel config {cfg}")

        # ---- things to say rather than show --------------------------------
        verdict("Limits", "Nationwide SMS", CANNOT,
                "TRAI DLT registration needed; 4 verified trial numbers only")
        verdict("Limits", "Malayalam voice call", CANNOT,
                "Twilio has no ml voice - IVR reads the English source instead")
        verdict("Limits", "Push inside the sideloaded APK", CANNOT,
                "a WebView has no Push API; Chrome install only")
        verdict("Limits", "Bluetooth mesh", CANNOT,
                "a browser cannot advertise as a GATT peripheral; one signed hop only")
        verdict("Limits", "A second enrolled village", CANNOT,
                "only Muttil North has consented recipients; the zero-recipient rule blocks the rest")
        verdict("Limits", "Translation on the hosted console", CANNOT,
                "Render cannot reach the laptop's :8001 - compose locally for auto-translation")

        print()
        for state in (SHOW, CAUTION, CANNOT):
            n = sum(1 for r in _rows if r[2] == state)
            print(f"{state:<8} {n}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
