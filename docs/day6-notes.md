# Day 6 (16 Aug) — what actually happened setting up the schema

Read this before touching migrations or `data/seeds/`. Five things that would
otherwise get rediscovered the hard way.

## 1. Local Postgres runs on port **5433**, not 5432

This laptop has a native `postgres.exe` Windows service already bound to
`0.0.0.0:5432`. Docker's container port mapping to 5432 silently "succeeded"
but every connection from the host was actually hitting the native service
instead — with a different password, and **neither side logged anything**,
which made it look like a docker-compose config bug for a while.

`infra/docker-compose.yml` now publishes the container on `5433:5432`.
Everything — `.env(.example)`, `services/api/settings.py`, `migrations/env.py`,
`run.py`, `scripts/doctor.py`, `scripts/wait_for_db.py` — was updated to match.

**If your machine doesn't have a conflicting native Postgres**, 5433 still
works fine; there's no reason to change it back. If you ever see
"password authentication failed" against a fresh container with the right
password, run `Get-NetTCPConnection -LocalPort 5432` (PowerShell) before
assuming the compose file is wrong.

## 2. `make` and `psql` are not on these machines — use `run.py`

No WSL2, no Makefile. `python run.py <task>` mirrors Part 37's Makefile
target-for-target (`python run.py db-up` = `make db-up`, etc.) so the spec's
prose still reads true. Every `psql` call in `run.py`/seed loading runs
**inside** the `setu-db` container via `docker compose exec`, so `psql` never
needs to be on PATH.

Use the venv's Python explicitly (`.venv/Scripts/python.exe` on Windows) —
`python3`/`py` on this machine resolve to 3.14, which has no wheels yet for
asyncpg/lxml/rasterio/lightgbm. The venv is pinned to 3.12.1.

## 3. `channel_capability` schema differs from §5.2/§8.2's SQL — on purpose

The spec's `channel_capability` table has ONE `not_applicable_reason` column
per channel. That's wrong the moment a channel fails more than one tier:
email is unsupported on both `device_delivered` and `opened`, and siren fails
three tiers — a single column prints the wrong reason against the wrong rung
(e.g. the tracking-pixel sentence rendered under "Device delivered" instead of
"Opened"), which directly undermines Rule 8.

Fixed in migration `0009_assurance.py`: **`channel_capability_tier`**, one row
per `(channel_id, tier)`, `CHECK (supported OR not_applicable_reason IS NOT NULL)`.
A **`channel_capability` view** still exists with the original one-row-per-
channel shape (via `bool_or(...) GROUP BY channel_id`) for any code that wants
the old convenience shape — but the per-tier reason lives in the tier table.
`AssuranceLadder.tsx` (when it's written) must read `channel_capability_tier`
directly to get the correct reason per rung, not the view.

## 4. Config-row counts in the spec don't match what's actually seeded

§21.4's heading says "36 rows" and Part 19's DoD asserts `app_config >= 74`
and `channel_capability = 8`. Neither number matches counting the actual
`INSERT`s (§21.4 has ~68 rows once you count every tuple; the per-tier
capability schema above produces 32 rows, not 8). `scripts/verify_seeds.py`
asserts against the **real, counted minimums** (71 app_config rows currently
seeded, 32 capability-tier rows, 13 escalation_policy rows), not the spec's
prose numbers. If you add config rows, bump the minimums in that script in
the same commit — don't let it drift back out of sync.

## 5. B10 (Community Relay Mode) needs a Day-4-ish spike before anyone builds on it

Web Bluetooth's `navigator.bluetooth.requestDevice()` connects as a GATT
**client**. No shipping browser exposes the GATT **peripheral/server** role to
a web page — which means Device A cannot advertise a service for Device B to
write to, and §8.7's `shareNearby()` as specced (`requestDevice` + `gatt.connect()`
on both ends) is not achievable phone-to-phone in a PWA.

`relay.peer_max_hops`'s `app_config` note flags this. **Confirm this before
anyone spends Day 7 on it** — 20 minutes with two Android phones and Chrome
DevTools settles it either way. If confirmed impossible, B10 is already
cut-order #4 (Part 16) with a kill switch (`relay.peer_enabled`), so the
Ed25519 signing/verification work (Rule 11) is still worth keeping regardless
— it's reused for the FCM push payload too.

## What's actually done as of tonight

- `git init`, `.gitignore`, venv on Python 3.12.1, `requirements.txt` pinned
  (`pip freeze`, 169 packages, PyNaCl included, zero torch/transformers).
- `infra/docker-compose.yml` — Postgres+PostGIS on 5433, Redis on 6379,
  MailHog on 8025. All three `healthy`.
- Migrations `0001`→`0012` applied. Round-tripped `head → 0006 → head` **twice**
  — once against an empty database, once with real seed data loaded — both
  clean.
- Seeds `01`–`05` applied (`05_relay_nodes.sql` correctly no-ops until the
  ADM3/ADM5 geometry load happens — it needs `admin_unit` rows that don't
  exist yet).
- `scripts/verify_seeds.py`, `scripts/doctor.py`, `scripts/gen_secrets.py`,
  `scripts/wait_for_db.py`, `scripts/guard_local_only.py`, `run.py` all written
  and working.
- Two real secrets generated locally (`PHONE_HASH_PEPPER`,
  `ALERT_SIGNING_SEED_B64` + its public counterpart) — **not shared here**;
  regenerate your own with `python scripts/gen_secrets.py` or get the team's
  shared value from the vault, never from a commit.

## Still open — tomorrow's actual blockers

- Neon account + both connection URLs (pooled + direct) — nothing here has
  touched the cloud database yet, only local Docker.
- Twilio account + verified numbers (relay-node seed is placeholder ciphertext
  and must be redone with real numbers before B9 work starts).
- FCM service account JSON + VAPID key pair (needed for the Day-5 push gate).
- ADM3/ADM5 geometry load (§1.6.2) — until `admin_unit` has rows, `relay_node`,
  `unit_features`, and both reachability/vulnerability views return nothing.
