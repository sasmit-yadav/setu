# Part 19 — Definition of Done, walked line by line

**Day 11 deliverable.** Part 16's Day-11 DoD is *"Full merged Definition of
Done (Part 19) walked line by line — every box ticked or explicitly waived
with a reason."* This is that walk.

**Walked:** 21 Aug 2026, against the running system — Postgres `:5433`,
Redis `:6379`, the live API, the built PWA bundle and real providers. Not
against `docs/IMPLEMENTATION.md`'s claims. Where a box could not be verified by
running something, it says so rather than being ticked.

**Legend:** ✅ verified now · ⚠️ partial, with the gap named · ❌ not done,
with what it needs · 🚫 waived, with the reason

**Standing numbers at walk time:** 267 tests passed / 2 skipped ·
`services/delivery` coverage **95.87%** · all six guard scripts green ·
`ruff check services/` clean · 196 `app_config` rows · 8 channels ·
32 capability tiers · 23 distinct audit event types.

**Re-checked after deployment (21 Aug, evening).** The stack is now live:
PWA https://setucitizen.vercel.app, API https://setu-api-6ujx.onrender.com,
Neon, Upstash. Boxes the deploy changed are marked *(deploy)*. It did **not**
move #3's push half, #12, #16 or #25 — those need a handset, a measurement, an
account and an artifact respectively.

---

## From v2.0/v2.1 — unchanged, still binding

| # | Box | Status | Evidence / reason |
|---|---|---|---|
| 1 | `git clone && make demo` on a fresh laptop | ❌ | *(deploy)* The repo is now on GitHub at `sasmit-yadav/setu`, so a clone is finally possible — before this there was no remote at all. Still untimed on a clean machine. Day 12 item. |
| 2 | PWA shows an alert + accepts an ack **with the cable unplugged** | ⚠️ | The data half is now real: after the service-worker fix, `setu-deliveries-v1` caches the alert *and* its safe zone, and the cached copy reads back headline, severity and Ed25519 signature with **no network**. The physical cable-pull with a human tapping ack is unrehearsed. |
| 3 | A real push **and** a real SMS arrive on real phones | ⚠️ | **SMS: done** — real `provider_accepted` (`twilio_sms_send`) then a real carrier callback writing `device_delivered` (`twilio_sms_webhook`, 60 rows), signature-verified, to a verified handset. **Push: not done** — `delivery_event` has **0** rows with `source='fcm_send'`. The credential authenticates against the real project; no token has been minted. |
| 4 | Every simulated delivery flagged in the DB **and** badged in the UI | ✅ | 308 rows with `simulated = true`; the `SIM` badge renders from that column (seen in the live PWA), and `channel_capability_tier` names sim's evidence source as `simulated_carrier_profile`. |
| 5 | Audit chain verifies, and `UPDATE audit_event` raises live | ✅ | `audit_immutable` trigger present on `audit_event` (`BEFORE UPDATE OR DELETE`). Confirmed incidentally during this work: three test alerts could **not** be deleted because the trigger refused. |
| 6 | Dedup precision/recall measured on a held-out set, published in the UI | ✅ | 200 labelled pairs in `data/ml/dedup_heldout.json`; P/R published to `model_registry` (4 rows) and rendered on the Methodology screen. |
| 7 | Reach-risk carries a visible **bootstrap** badge + disclosure text | ✅ | `reach_risk.disclosure.missing` seeded in `app_config`; `is_bootstrap` never cleared; `RiskDial` renders the badge. |
| 8 | `/api/v1/methodology` returns every threshold, metric, limitation | ✅ | Route registered and serving; drives the Methodology screen. |
| 9 | `check_no_hardcoding.py` passes in CI | ✅ | Green, three passes (Python AST · SQL views · TS), wired in `.github/workflows/ci.yml`. |
| 10 | **Branch coverage ≥95% on the delivery state machine, re-verified after every v3.0 writer** | ✅ | **95.87%**, re-run after B3's writers were added — which is exactly the re-verification this box asks for. `state_machine.py` and `states.py` are both at 100%. |
| 11 | All six teammates can run the demo alone | ❌ | Day 12–13 rehearsal. Needs the team. |
| 12 | Redis command budget ≥5× headroom | ⚠️ | *(deploy)* Re-derived from real data (33 dispatches): found B3's idle-tick `ZPOPMIN` cost **17,280 commands/day alone**, exceeding the whole daily budget before any alert fires. Fixed by raising `delivery.xread_block_ms` 5000→15000 (config, not a literal). At a generous 4-hour continuous run: **4.08× headroom** — short of 5× unless the worker is stopped between rehearsals, which the evidence doc states plainly rather than rounding up. `docs/evidence/redis-budget-2026-08-21.md`. |
| 13 | USGS/GDACS ingestion, zero auth, confirmed live | ✅ | Both adapters run against the live zero-auth endpoints; 218 `alert.ingested` audit events. GDACS uses `/SEARCH` (the spec's `/MAP` 400s without `eventtype`). |
| 14 | Thunderstorm nowcast scores a real India district from live Open-Meteo | ⚠️ | `ThunderstormNowcastAdapter` exists and is unit-tested, but its `alert_source` row is seeded `enabled = false`, so it has never polled live. The seed comment ("enabled once the adapter exists") is stale now that it does. |
| 15 | Citizen PWA resolves a nearest safe zone from real OSM rows | ✅ | Verified in the live PWA: *"Community Hall, Muttil · community_centre · 820 m"*, from the 281 Overpass-sourced `safe_zone` rows, with the road-conditions disclosure. |
| 16 | Translation runs on the 200M model on the actual free-tier host | ❌ | No HF Space deployed. `HF_SPACE_URL` is a placeholder. The API caches over HTTP only and never imports torch; PWA/IVR/relay fall back with a visible notice. |
| 17 | `app_config` + extended `escalation_policy` seeded — every threshold a row | ✅ | 196 config rows, **0** with an empty note (three `severity.rank` rows were blank; fixed), 13 escalation-policy rows. `verify_seeds.py` now *fails* on drift instead of printing INFO. |
| 18 | `services/ml` runs as its own Space; `services/api` has zero torch imports | ⚠️ | The isolation is real and enforced — `check_no_torch.py` green, `python run.py ml` runs `services.ml.server` on `:8001`, weights load only under `SETU_LOAD_ML_MODELS=1`. *(deploy)* The Space image is now **built and run-tested**: `/health` reports honestly, `/translate` returns 503 `models_absent` instead of crashing, and a wrong `X-Internal-Key` returns 401. The *hosting* half is still not done (see #16). |
| 19 | Pooled URL for the app, direct URL for migrations | ✅ | `DATABASE_URL_POOLED` / `DATABASE_URL_DIRECT` split in `settings.py`; `alembic` uses the direct DSN. |
| 20 | **Retry backoff shows visible growth + jitter in a captured log from a forced-failure test** | ✅ | **This was unsatisfiable until today** — B3 was dead code (see §6.13). `docs/evidence/backoff-2026-08-21.md` is generated from the live policy rows: growth 60 → 90 → 135 s, jitter spread ±2.5 s, mean on the policy curve. Pinned by 16 tests. |
| 21 | `.env.example` and the Part 25 table match; CI fails on drift | ✅ | `check_env_example.py` green. Grew by six keys today (five Firebase + `PGCRYPTO_SYM_KEY`). |
| 22 | RBAC matrix is a table in the repo and every row has a test | ✅ | Part 26 is the table; **140** RBAC tests. Three rows had no allow/deny pair (`/units/{id}/vulnerability`, `POST /response`, `POST /citizen/device`) and now do. |
| 23 | `freeze-guard.yml` live, and its block demonstrated once deliberately | ⚠️ | Live, guarding all Day-11 paths, epoch 21 Aug 21:00 IST. The block **cannot** be demonstrated until that timestamp passes — a few hours out at walk time. |
| 24 | Redis-budget and health-check webhook pings each fired once | ❌ | `SLACK_OR_DISCORD_ALERT_WEBHOOK` is empty. Needs a webhook URL. |
| 25 | Four-tile DEM check has a committed, dated pass/fail log | ✅ | *(deploy)* Run for real against the Copernicus S3 bucket with `--no-sign-request`. Part 29's own literal command uses the wrong prefix (`COG_30`); corrected to `COG_10` (confirmed by listing), all 4 tiles present for Wayanad + Palghar, no SRTM fallback needed. `docs/evidence/dem-four-tile-check-2026-08-21.md`. |
| 26 | Total spend: **₹0** | ✅ | Everything used is free-tier: Firebase Spark, Twilio *trial credit* (not purchased), ngrok free, Neon free, local Docker. No card charged. |

## [v3.0] Structural

| # | Box | Status | Evidence / reason |
|---|---|---|---|
| 27 | Migrations `0007`–`0012` applied, **every down-revision tested** | ✅ | Re-proven today on a **scratch database** so local data survived: `upgrade head → downgrade 0006 → upgrade head`, clean. Chain now runs to `0014`. |
| 28 | Every new table has ≥1 real, non-mock row | ✅ | All 12 checked: `incident` 1955, `alert_approval` 92, `alert_validation_result` 60, `delivery_event` 1095, `citizen_response` 140, `assistance_case` 86, `relay_node` 29, `relay_confirmation` 23, `alert_translation` 114, `reach_prediction` 171, `channel_capability_tier` 32, `refresh_token` 53. |
| 29 | Every new threshold is an `app_config` row **with a non-empty note** | ✅ | 0 empty notes, and `verify_seeds.py` now fails on it rather than reporting. |
| 30 | `check_no_hardcoding.py` green on `governance/` and `response/` **specifically** | ✅ | Both directories are in the guard's scan list (verified by reading it, not assuming). |
| 31 | `check_channel_capability.py` green — adapter flags match the table | ✅ | Green. This guard is what caught `PeerRelayAdapter` contradicting its seeded tiers (a Rule 8 violation, §6.12). |
| 32 | All five new property tests green (Part 13) | ✅ | `test_assurance_level_is_monotonic`, `test_csv_import_is_idempotent`, `test_no_channel_reports_unsupported_tier`, `test_single_officer_cannot_satisfy_quorum`, `test_tampered_relay_payload_is_never_accepted`. |
| 33 | Both new chaos tests green | ✅ | `tests/unit/test_chaos_webhooks_and_queue.py` — duplicate/out-of-order webhooks and Redis flush + queue rebuild. |
| 34 | `test_snapshot_completeness.py` green **against the final Day-11 snapshot** | ✅ | Final snapshot `data/snapshots/2026-08-21.json` cut and committed; `verify_snapshot --latest` clean, 24 tables; test green against it. |

## [v3.0] Honesty — each is a way the release could have lied

| # | Box | Status | Evidence / reason |
|---|---|---|---|
| 35 | **No channel reports a tier it cannot prove** — verified in the *rendered UI*; SMS's "Opened" struck through with its reason | ✅ | 0 unsupported tiers lack a `not_applicable_reason`. `AssuranceLadder` renders the strike-through plus the verbatim reason and an `sr-only` announcement; confirmed live on a real siren delivery (3 struck rungs) and locked by `test_a11y_source.py`. |
| 36 | Human relay confirmations **visibly distinct** — `HUMAN` chip, UI and PDF | ✅ | Stored in a separate `relay_confirmation` table (Rule 9 enforced by the schema split, not by hiding a tier); chip renders in the console and the report. |
| 37 | A relayed alert shows `⇄ PEER · signature verified` + one-hop disclosure | ✅ | Renders in the citizen PWA (`IconPeer`, `peerProvenance`), with the "one hop, not a mesh" text. Signature verification is real; only the *Bluetooth transport* is unproven (#54). |
| 38 | **Reachability shows both denominators**, each labelled with `geometry_level` | ✅ | Verified on real data — unit 5179: **38.2%** of registered recipients, **1.5%** of estimated population, `geometry_level = 3`. Exactly the gap the two-denominator design exists to expose. |
| 39 | Lead-time publishes its own `coverage_pct` and excludes seismic with a reason | ✅ | `/analytics/lead-time` returns p10/p50/p90, `coverage_pct`, `excluded_seismic_count` and the stated reason. |
| 40 | Every assistance case's `priority_factors` non-NULL, breakdown renders | ✅ | 86 cases, **0** NULL. Each carries all 5 factors + the weight set + `weight_version` (`v1-2026-08-16`). Rule 10 satisfied. |
| 41 | Command Board contains **zero hardcoded values** — verified by grep | ✅ | `grep` over `CommandBoard.tsx` for numeric literals returns only an HTTP 403 status check. Board router likewise clean; `board.worst_units_limit` comes from config. |

## [v3.0] Behavioural

| # | Box | Status | Evidence / reason |
|---|---|---|---|
| 42 | Quality gate **blocks a genuinely invalid alert live**, reason adjacent to the disabled button | ✅ | Exercised over real HTTP today: alert with no expiry → `blocked: true`, failing rules named (`expiry_set`, `translation_exists`). `QualityGate` renders the reason next to the disabled dispatch button, never a toast. |
| 43 | Dual auth with **two distinct real logins on two devices**; one officer cannot self-quorum | ⚠️ | The *guarantee* is proven: 1 approval → 409 `{have:1,need:2}`; a second distinct officer unlocks dispatch; the same officer twice yields **one** `alert_approval` row **and one** `alert.approved` audit row. The two-physical-devices choreography is Day 12's 10× rehearsal. |
| 44 | An authoritative-source alert dispatches with **zero** human steps; a human-composed extreme does not | ✅ | `alert_approval` holds a real `provenance='authoritative_source'` row alongside 55+ `human` rows, and the auto-approval is now audited too. |
| 45 | A superseded version's in-flight deliveries expire with `reason='superseded_by_version'` | ✅ | `alert_one_active_per_incident_uix` confirmed live; supersede path sets the reason; `failed_reason` is a real column that is actually written (§6.12's fix). |
| 46 | Fatigue relabels a repeat and **provably never suppresses** an extreme alert | ✅ | `apply_headline()` structurally cannot suppress — it only ever returns the headline, optionally prefixed — which is stronger than a test. The Day-8 test now pins it anyway, plus idempotency (no double-prefix on retry). |
| 47 | CSV import **provably idempotent** on a second identical run | ✅ | `tests/property/test_csv_import_is_idempotent.py` green; mandatory `dry_run` first, `phone_hash` dedupe. |
| 48 | `STOP` sets `opted_out_at` and that recipient is **never enqueued again** | ✅ | **Had no test at all until today**, despite being a consent guarantee. Now four tests cover the whole path: the keyword writes the timestamp, the ledger records it, and `recipients_in_area()` stops returning them — for a *new* alert after the opt-out. |
| 49 | A `relay.unavailable` audit event exists for a unit with no relay coverage | ✅ | 5 rows. The platform can name where its last resort is missing. |
| 50 | A relay-node token requesting `/assistance` gets **403** | ✅ | In the RBAC suite; §12.2's hardest row. `relay_node` gets count+area via `/assistance/summary` only. |
| 51 | Gate 3 offline test passes with every new feature active, re-confirmed Day 11 | ⚠️ | The caching half now works for the first time (SW fix). The physical unplug re-run is outstanding. |
| 52 | The **21-step integration run** in one unbroken recorded take | ❌ | Not done. Needs all six people, real phones and a screen recorder. The single largest outstanding item in the whole roadmap. |
| 53 | Two-person approval choreography rehearsed **10×** consecutively | ❌ | Day 12. Needs two humans on two devices. |
| 54 | Device decision written into `docs/demo-device.md`, not revisited after Day 8 | ✅ | Android Chrome, with the reasoning (covers both offline-PWA and Web-Bluetooth weak spots) and the pre-agreed fallback to a recording if Bluetooth fails twice. |

## Part 38 — the two audits

| # | Box | Status | Evidence / reason |
|---|---|---|---|
| 55 | All five Part 38.1 hardcoding violations fixed; guard runs all three passes + TwiML test | ✅ | Green. Guard strengthened during §6.12 to see *default arguments* (it previously only inspected `Compare`/`BinOp`), and verified to actually fail on a probe file before being trusted. |
| 56 | `verify_seeds.py` asserts 74 `app_config` and 8 `channel_capability` rows before anything starts | 🚫 **Waived, deliberately** | The script asserts ≥110 config rows and 32 `channel_capability_tier` rows instead, and says why in its own docstring: the spec's "74 / 8" is stale, and `channel_capability` became a *view* over a 4-tiers × 8-channels table in migration `0009` because one `not_applicable_reason` column cannot hold a reason per tier. Asserting the spec's numbers would make this script the second place the count drifted, not the fix for the first. |
| 57 | **The basemap renders with the network unplugged** — verified during a Gate-3 run | ⚠️ | The file is committed and configured: 2.6 MB `setu-basemap.pmtiles`, `map.tile_source = pmtiles_local`. Not yet verified *during an actual unplugged run*, and place-name glyphs still hit a CDN when online (village names are HTML labels and work without them). |
| 58 | Twilio credit ≥2 voice calls and ≥5 SMS at T-30 min; B6/B9 rehearsed on the simulated adapter | ⚠️ | Credit is ample: **$9.32**, ≈112 SMS at the measured ₹7/message India rate. Voice costs more per attempt and has never been exercised, so the *rehearsal* half of this box is not done. |
| 59 | **Class ⑤ (fabricated) is empty** — walked screen by screen | ⚠️ | The architecture enforces it: §7.5 records every console figure as class ①–④, `check_no_hardcoding` covers the board, the Command Board grep is clean, and D7f/D11f/D12f all render stored inputs. A deliberate screen-by-screen walk of the *rendered* UI, which is what this box asks for, has not been performed. |

---

## Summary

Re-tallied 21 Aug (evening) after #12 and #25 were closed with real
measurements rather than left as assumptions.

| Status | Count |
|---|---|
| ✅ Verified | **41** |
| ⚠️ Partial, gap named | **11** |
| ❌ Not done | **6** |
| 🚫 Waived with reason | **1** |
| **Total** | **59** |

(Re-counted directly from the table's own status column, not carried forward
by arithmetic — the two prior tallies in this document's history had drifted
from what the rows actually said.)

**Every ❌ and every ⚠️ shares one of four causes**, none of which is unwritten
code:

1. **No HTTPS deploy** — real FCM push, the SW receipt, Gate 3 on a handset.
2. **No second human / no phone answered** — IVR, B9 DTMF, dual-auth
   choreography, the 21-step take, the six run-throughs.
3. **No second device** — B10 Bluetooth (and `§8.1` flags it as possibly
   impossible in a browser: **spike before budgeting engineering time**).
4. **An account we do not have** — HF Space for IndicTrans2, a Discord/Slack
   webhook for monitoring.

**(deploy)** — #25 and #12 were the two exceptions: neither blocked nor done,
just unmeasured. Both closed same-day: the DEM check found all four tiles
present (once Part 29's own command was corrected), and the Redis re-derivation
found a real problem — B3's idle polling alone exceeded the daily budget — and
fixed it with a one-line config change, landing at 4.08× headroom rather than
the stated 5×.
