# SETU — Implementation Reference

This is the living technical reference for what's actually built, how it's built,
and why. It is derived from `docs/SETU_MASTER_v3.0_MERGED.md` (the design spec)
but is **not a copy of it** — this doc tracks reality: what deviates from the
spec, what was fixed, what's still open, and the concepts underneath the code.

When the spec and this doc disagree, **this doc wins** — it reflects what's
actually running. Update it in the same commit as the code change it describes.

For "what to do next," see `TASK.md`, not this file. This file is "how does it
work and why," not "what's left."

---

## 1. What SETU is, in one paragraph

A disaster-alert platform that doesn't just send warnings — it proves whether
one was *authorized*, *delivered to a device*, *understood*, and *acted on*,
and it's explicit in the UI and the database about every one of those claims
it **cannot** prove. The product's central discipline: a channel or a model is
never allowed to claim a stronger evidence tier than it can actually produce.
Where evidence doesn't exist (SMS read receipts, siren delivery confirmation,
earthquake lead time), the platform says so, in a database column, rendered
verbatim, rather than showing a flattering number.

## 2. Core concepts — the ones that shape the schema

### 2.1 The delivery state machine is separate from the assurance ladder

`delivery.state` (8 values: pending → queued → sent → delivered → acknowledged
/ failed / expired / escalated) is the **transactional lifecycle** — what a
delivery is *doing right now*. It is intentionally small, `FOR UPDATE`-locked,
and never touched by the v3.0 work.

`delivery_event` is a **separate, append-only evidence log** sitting beside
it — six tiers (`delivery_attempted` → `provider_accepted` →
`device_delivered` → `notification_opened` → `acknowledged` →
`citizen_response`), one row per tier per delivery
(`UNIQUE(delivery_id, event_type)`), written by adapters and webhooks. A
delivery's assurance level is *derived* from these rows via the
`assurance_level()` SQL function — never stored as a column that could drift
from its own evidence.

These two answer different questions and are combined in exactly one place:
an `acknowledged` assurance event also calls `transition(state=acknowledged)`
in the same transaction, because that *is* the pre-existing ack path.
Everything else is one-directional: assurance events never drive a state
transition.

### 2.2 The honesty ladder — capability is data, not code

Every channel (fcm, email, sms, ivr, siren, sim, human_relay, community_relay)
declares, per adapter class, which of four tiers it can prove:
`provider_accept`, `device_delivered`, `opened`, `acknowledgement`. That
declaration is mirrored in the database (`channel_capability_tier`) rather
than trusted to match — a CI check (`check_channel_capability.py`, not yet
written) is meant to fail the build if the adapter's declared flags and the
table disagree.

**Where a tier is unsupported, `not_applicable_reason` is mandatory**
(`CHECK (supported OR not_applicable_reason IS NOT NULL)`) and is rendered
verbatim in the UI, struck through — never greyed (reads as loading), never
hidden (reads as "we didn't check").

> **Deviation from the spec, and why:** §5.2/§8.2 model this as ONE
> `not_applicable_reason` column per channel. That's wrong the moment a
> channel fails more than one tier — e.g. email fails both `device_delivered`
> (no pixel tracking) and `opened` (same reason), and siren fails three tiers.
> A single column prints the *wrong* reason against the wrong rung. Built
> instead as `channel_capability_tier(channel_id, tier, supported,
> device_delivered_source, not_applicable_reason)` — one row per
> `(channel, tier)` pair. A `channel_capability` **view** still exists with
> the original one-row-per-channel shape (`bool_or(...) GROUP BY channel_id`)
> for code that wants that convenience shape, but any UI rendering a specific
> unsupported rung must read the tier table directly to get the right reason.
>
> **CI enforcement:** `scripts/check_channel_capability.py` imports every
> adapter class_path from the DB and asserts its boolean tier flags match
> `channel_capability_tier`. Runs green locally and in `.github/workflows/ci.yml`.

### 2.3 Human attestation is never digital delivery evidence

`relay_confirmation` (a village officer physically informing households
where every digital channel failed) is a **separate table**, separate event
type, separate UI treatment. `households_claimed` is named `_claimed`, not
`_reached` — a human's self-report over a phone keypad, and the column name
is the first defence against a report later presenting it as verified fact.

### 2.4 An alert's lifecycle is versioned, and only one version is ever active

`incident` groups related alert versions. `alert` gained
`incident_id`, `version_number`, `supersedes_alert_id`, `change_reason`,
`lifecycle_status`. A partial unique index —
`alert_one_active_per_incident_uix ON alert(incident_id) WHERE
lifecycle_status = 'active'` — makes "two contradictory live warnings for one
incident" a database error, not an operational ambiguity. Superseding an
alert expires any still-`pending`/`queued` deliveries of the old version
(already-`sent` ones are left alone — you cannot unsend a message).

### 2.5 Governance: human origin needs human approval; machine origin records provenance

`alert_source.is_authoritative` decides the path. USGS and GDACS are
`true` — an external authoritative feed auto-approves
(`alert_approval.provenance = 'authoritative_source'`, `approver_id IS NULL`).
A human-composed alert, or SETU's own thunderstorm nowcast model
(`is_authoritative = false` — **our own model doesn't get to approve its own
extreme alerts**), needs N distinct human approvals depending on severity
(1 for minor/moderate, 2 for severe/extreme), enforced by
`UNIQUE(alert_id, approver_id)` — one officer clicking twice can never
satisfy a two-person quorum.

### 2.6 Every derived score stores the inputs that produced it

`assistance_case.priority_factors` (D11f) and `reach_prediction.features`
(reach-risk) are `NOT NULL JSONB` — a score is never a black box. The
priority formula itself is a plain weighted sum over five factors read from
`app_config`, not a trained model — deliberately, since there's no historical
triage-outcome data to train on yet, and an unexplained learned ranker would
be strictly worse than an explainable formula for an officer who has to
justify a queue order.

### 2.7 Consent is structural, not just checked in application code

`recipient` requires `consented_at` before any individually-addressed channel
(push/SMS/email/IVR) will enqueue to them — enforced by a property test, not
just a code path. `citizen_response.location` has
`CHECK (location IS NULL OR location_consent = true)` — a bug that forgets to
check consent in application code *cannot* write a location; the insert
fails. Two channel classes reach people **without** needing their consent,
because they don't process personal data: area-broadcast (siren) and human
relay (a person knocking on a door isn't processing anyone's phone number).

### 2.8 Deterministic dedup key vs. randomized encryption

`recipient.phone_enc` is `pgcrypto`'s `pgp_sym_encrypt`, which is
**randomized by design** — encrypting the same number twice produces
different ciphertext, so `UNIQUE(phone_enc)` never fires and CSV re-imports
would silently duplicate every recipient. Fixed with a parallel
`phone_hash BYTEA` column — an HMAC-SHA256 of the E.164 number under a
server-side pepper (`PHONE_HASH_PEPPER`), which **is** deterministic and
carries the actual unique index. `phone_enc` stays for the audited reveal
path; `phone_hash` is what dedupe/enrollment/STOP-lookup use. Never logged —
it's a stable pseudonymous identifier and still personal data.

---

## 3. Stack — what's actually installed, and why each piece

### 3.1 Backend — Python 3.12.1 (not 3.14)

| Piece | Package | Why |
|---|---|---|
| API framework | `fastapi` | async-native; dependency injection carries RBAC |
| Validation | `pydantic` v2 + `pydantic-settings` | 422 on malformed input, never reaches a query |
| ASGI server | `uvicorn` | standard |
| DB driver (runtime) | `asyncpg` | async, used behind the **pooled** URL |
| DB driver (migrations) | `psycopg[binary]` (v3) | used behind the **direct** URL — see §4 below |
| ORM/engine | `sqlalchemy[asyncio]` | connection pooling; raw SQL for the delivery hot path |
| Migrations | `alembic` | one revision per schema change, tested down-revisions |
| Redis | `redis` (redis-py async) | Streams, consumer groups, ZSETs, pub/sub |
| HTTP | `httpx` | every outbound fetch, explicit timeouts everywhere |
| Scheduler | `apscheduler` | in-process ingestion poll loop, no extra service |
| CAP parsing | `lxml` | defensive XML parsing, survives malformed input |
| Geometry | `shapely`, `pyproj` | CAP circle→polygon, sanity checks pre-PostGIS |
| Channels | `twilio`, `firebase-admin` | SMS/IVR/relay; FCM push |
| Signing | `pynacl` | Ed25519 alert signing — ~2MB, **zero torch dependency** |
| ML (small) | `lightgbm`, `numpy`, `pandas`, `scikit-learn` | reach-risk model; a few MB, fits in 512MB free tier |
| Rate limiting | `slowapi` | per-IP/per-token, tighter on `/dispatch` |
| Logging | `structlog` | structured, with a PII-redaction filter |
| Metrics | `prometheus-fastapi-instrumentator` | |
| Errors | `sentry-sdk` | disabled during load tests |
| Build-time only | `rasterio` | WorldPop/DEM zonal sampling — never in the request path |

**Hard rule, enforced by CI (not yet written):** `services/api` must never
import `torch` or `transformers`. Those live only in the separate ML service
(§3.3) — this is the fix for a 512MB Render OOM that would otherwise be
discovered on stage.

**Why 3.12, not the system default 3.14:** `python3`/`py` on this machine
resolve to 3.14, which currently has no wheels for `asyncpg`, `lxml`,
`rasterio`, `lightgbm`. The venv (`.venv/`) is built against
`python` → 3.12.1 explicitly. Always invoke `.venv/Scripts/python.exe`
(or activate the venv), never the bare `python3`/`py` aliases.

### 3.2 Database — Postgres 16 + PostGIS 3.4

Local: `postgis/postgis:16-3.4` in Docker, **published on host port 5433, not
5432** (see §4.1 — a native Windows Postgres service already owns 5432 on
this machine). Extensions: `postgis`, `pgcrypto`, `pg_trgm`.

Two connection URLs, never one (`DATABASE_URL_POOLED` for the app runtime,
`DATABASE_URL_DIRECT` for migrations) — transaction-mode connection pooling
(what a hosted pooler like Neon's `-pooler` endpoint does) breaks
session-level DDL, which is why migrations must bypass the pool entirely.

### 3.3 ML service — not yet built, but scoped

Will be its own deployment target (originally spec'd as a Hugging Face
Space) so `torch`/`transformers` never load inside the API process. Two
endpoints: `/embed` (dedup clustering) and `/translate` (IndicTrans2). Not
started yet — no ML code exists in this repo.

### 3.4 Frontend — citizen PWA shipped; console not started

| App | Path | Status |
|---|---|---|
| Citizen PWA | `web/citizen/` | ✅ MVP — Vite + React + Workbox service worker |
| Officer console | `web/console/src/` | ⚪ empty — next build priority |

**Citizen PWA (`web/citizen/`):** offline-capable alert viewer and response
flow. All runtime tuning (PWA cache timeouts, BackgroundSync retention,
`response.free_text_max_chars`) comes from `GET /api/v1/public/config` —
no hardcoded fallbacks in `App.tsx` or `sw.ts` (enforced by
`scripts/check_pwa_config.py` in CI). Ed25519 verify key from env
(`VITE_ALERT_SIGNING_PUBKEY_B64`) or `GET /api/v1/public/signing-key`.
Push notifications require Firebase + VAPID (blocked — manual delivery ID
works for dev). Dev server proxies `/api` → `localhost:8000` in
`vite.config.ts` only — not a production config path.

**Officer console:** planned dark-first ops UI for compose → preview →
validate → approve → dispatch. Backend routes exist; no React code yet.

### 3.5 Local infrastructure

`infra/docker-compose.yml` — three services:

| Service | Image | Host port | Notes |
|---|---|---|---|
| `db` | `postgis/postgis:16-3.4` | **5433** (not 5432) | see §4.1 |
| `redis` | `redis:7-alpine` | 6379 | append-only enabled |
| `mailhog` | `mailhog/mailhog` | 1025 (SMTP), 8025 (UI) | captures dev email, no real quota spent |

---

## 3.6 Live external data sources — verified, not assumed

`scripts/verify_data_sources.py` hits every live/build-time data source the
design spec names (§1.1, §1.2, §1.6) and reports LIVE/FAIL/SKIP. Run it any
time a source starts misbehaving — it's meant to be the first thing checked,
not a one-off. Result **at the time this check was first run**: 14/15 live,
0 failed, 1 skipped (OpenCelliD — no token yet). **The token has since been
obtained and the download fully solved — see §5.5** for the real URL shape
and the honest zero-India-rows finding. This section's numbers describe
what the script reported that day, not the OpenCelliD situation today.

Two of those "live" results required fixing the spec's own fetch commands
first — both are the kind of bug that would otherwise surface as a confusing
partial failure on the day someone actually runs the geometry load:

### geoBoundaries admin boundaries are Git-LFS-tracked

The spec's fetch command (§1.6.2) is
`curl -fSL -o ... raw.githubusercontent.com/wmgeolab/geoBoundaries/.../*.geojson`.
That host returns the **LFS pointer text** for an LFS-tracked file — a ~130
byte text blob (`version https://git-lfs.github.com/spec/v1\noid sha256:...\nsize ...`),
not the actual geometry. `ogr2ogr` handed that file would fail outright, or
worse, silently accept something malformed.

**Fix:** use `media.githubusercontent.com/media/<same path>` instead —
GitHub's LFS media proxy. Confirmed: ADM3 → 40,040,002 bytes (~38MB, matches
the spec's own size claim); ADM5 → 467,134,382 bytes (~445MB, also matches).
`scripts/fetch_data.sh` uses the correct host and additionally refuses to
proceed if either downloaded file is under 1MB — a cheap, permanent guard
against this exact failure mode recurring silently.

### Copernicus DEM tile keys are named `COG_10`, not `COG_30`

The spec's DEM fetch script and Part 29's four-tile check both build the S3
key as `Copernicus_DSM_COG_30_{tile}_DEM`. The bucket is genuinely named
`copernicus-dem-30m`, but **every key inside it is actually named
`Copernicus_DSM_COG_10_{tile}_DEM`** — confirmed by listing the bucket
directly for the four Wayanad/Palghar tiles
(`N11_00_E076_00`, `N19_00_E072_00`, `N19_00_E073_00`, `N11_00_E077_00`).
Using the spec's literal key 404s on all four tiles and would wrongly
trigger Part 29's "MISSING: fall back to SRTM" path for a source that is
actually fully present. `scripts/fetch_data.sh` uses `COG_10`.

### Smaller findings, not bugs, worth knowing

- **GDACS**: `/gdacsapi/api/events/geteventlist/MAP` requires an `eventtype`
  param (400 without one) — the spec's bare URL example was incomplete.
  `/gdacsapi/api/events/geteventlist/SEARCH` needs no params and returns
  live global events directly; use that for the ingestion adapter instead.
- **WorldPop**: the spec's exact filename
  (`Global_2000_2020_Constrained/2020/BSGM/IND/ind_ppp_2020_UNadj_constrained.tif`)
  is correct as written — confirmed a real 489MB TIFF. (The WorldPop REST
  *listing* API defaults to a different, unconstrained dataset series if you
  query it generically — don't use that path to "verify" this file; it
  reports success without ever touching the real one.)
- **IMD**: `/public/` alone is the API-management portal's HTML landing
  page (200), not a data endpoint — a 200 there does *not* mean the API is
  open. No documented endpoint path could be found to actually test Trap 2's
  401 claim without registering. Still correctly not on the critical path.
- **Google Open Buildings**: no stable discovery API exists; per-district S2
  cell IDs genuinely have to be resolved at build time, exactly as the spec
  says. Not further verifiable generically.
- **Protomaps basemap**: `build.protomaps.com` root 404s (expected — it
  serves date-stamped build files, not a directory index). Host is live;
  the actual current build filename is a `[RECONFIRM]`-at-load-time item,
  not something a static check can resolve.

---

## 4. Environment quirks found while building — read before debugging

### 4.1 Local Postgres runs on port 5433

This machine has a native `postgres.exe` Windows service already bound to
`0.0.0.0:5432`. A container also mapped to 5432 will *appear* to start fine,
but every TCP connection to `localhost:5432` from the host silently hits the
native service instead of the container — with a different password, and
**neither side logs an error that explains why** (the container never sees
the connection attempt at all).

Fix: `infra/docker-compose.yml` publishes the container on `5433:5432`. Every
reference to the connection string —
`.env`, `.env.example`, `services/api/settings.py`, `migrations/env.py`,
`run.py`, `scripts/doctor.py`, `scripts/wait_for_db.py` — uses 5433.

If you hit "password authentication failed" against a container you just
created with the *correct* password, check for a port conflict first
(`Get-NetTCPConnection -LocalPort 5432` in PowerShell) before assuming the
compose file or `.env` is wrong.

### 4.2 No `make`, no `psql`, no WSL2 on these machines

`run.py` is a plain-Python task runner mirroring the spec's Makefile
target-for-target (`python run.py db-up`, `python run.py db-migrate`, etc.).
Every SQL operation it runs against the local stack goes through
`docker compose exec -T db psql ...` — so `psql` never needs to be on the
host `PATH`. Windows PowerShell and Git Bash can both call it identically.

### 4.3 SQLAlchemy needs the driver named explicitly

A bare `postgresql://` URL (what Neon and most docs hand you) makes
SQLAlchemy default to `psycopg2`, which is **not** in `requirements.txt` —
this repo pins `psycopg[binary]` (v3) instead. `migrations/env.py` rewrites
`postgresql://` → `postgresql+psycopg://` before creating the engine, so
`.env` can stay in the exact form any provider (Neon included) hands you.

### 4.4 Windows console encoding

`scripts/gen_secrets.py` (and anything else printing box-drawing/Unicode
punctuation) must call `stream.reconfigure(encoding="utf-8")` on
`sys.stdout`/`sys.stderr` — the default Windows console codepage (cp1252)
raises `UnicodeEncodeError` on `─`, `→`, etc. otherwise.

### 4.5 Never `source` a `.env` file with unquoted values containing `&`

Neon's connection strings include `?sslmode=require&channel_binding=require`.
Doing `set -a && source .env.neon && set +a` in bash — the exact pattern used
throughout this session for one-off local Postgres testing — **silently
produces an empty variable** for any value containing a bare `&`:

```bash
X=postgresql://user:pass@host/db?sslmode=require&channel_binding=require
echo "[$X]"   # → []
```

Bash treats the unquoted `&` as the background-job operator even with no
surrounding whitespace: `X=...&channel_binding=require` backgrounds the
`X=...` assignment (which sets `X` only inside a throwaway subshell, never
the parent shell) and then evaluates `channel_binding=require` as a second,
unrelated, no-op assignment. Nothing errors — `alembic upgrade head` ran
against `migrations/env.py`'s hardcoded local-Postgres fallback instead of
Neon, and appeared to succeed (because the local DB genuinely was already at
head), which is a worse failure mode than a crash would have been.

**Fix, applied everywhere:** quote every value in every `.env*` file —
`DATABASE_URL_DIRECT="postgresql://...&channel_binding=require"` — so
`source`/`export` handle them correctly regardless of what characters the
value contains. Local `.env`'s bare `postgresql://setu:setu@localhost:5433/setu`
URLs never had a `&` in them, which is exactly why this stayed hidden until
the first Neon connection string was sourced.

**`run.py`'s `load_env()` function was never affected** — it parses `.env`
itself in Python (`line.partition("=")`, no shell involved), which is
correct precisely because it never asks a shell to interpret the value. The
bug only bites ad-hoc `source` invocations from a terminal, which is exactly
how the Neon verification was first attempted.

---

## 5. Database schema — as actually built

### 5.1 Migration chain

| Rev | Adds | Down-tested? |
|---|---|---|
| `0001_extensions_and_geography` | `postgis`/`pgcrypto`/`pg_trgm`; `admin_unit`, `unit_features`, `safe_zone` | ✅ |
| `0002_config_and_sources` | `app_config`, `alert_source`, `channel`, `escalation_policy` | ✅ |
| `0003_ml_registry` | `model_registry` (needed by `alert_translation`/`reach_prediction` FKs) | ✅ |
| `0004_alerts` | `alert`, `alert_quarantine`, `alert_translation` (base columns only) | ✅ |
| `0005_recipients_and_delivery` | `recipient`, `delivery_state` enum, `delivery` (base columns only) | ✅ |
| `0006_audit_and_reach_prediction` | `audit_event` + append-only trigger, `reach_prediction` | ✅ |
| `0007_incident_lifecycle` | `incident`; `alert` lifecycle columns; `alert_one_active_per_incident_uix`; backfills existing alerts into single-version incidents | ✅ |
| `0008_governance` | `app_user`, `alert_approval`, `alert_validation_result` | ✅ |
| `0009_assurance` | `assurance_event` enum, `delivery_event`, `assurance_level()` function, `channel_capability_tier` + `channel_capability` view, `audit_event.incident_id` | ✅ |
| `0010_citizen_response` | `citizen_response`, `assistance_case` | ✅ |
| `0011_relay` | `relay_node`, `relay_confirmation` | ✅ |
| `0012_enrollment_and_views` | `recipient.phone_hash`/`consent_source`/`opted_out_at` (+ unique index, backfill); views `v_reachability`, `v_communication_vulnerability`, `v_lead_time`, `v_lead_time_coverage` | ✅ |

**`0012` fails loudly** (raises, does not proceed) if `PHONE_HASH_PEPPER` is
unset — writing NULL hashes would leave the unique index inert and silently
reintroduce the dedup bug it exists to fix.

**Verified twice:** `alembic upgrade head → downgrade 0006 → upgrade head`
against (a) an empty database and (b) a database with all seed data loaded.
Both clean. Note: a downgrade past `0009` drops `channel_capability_tier`
along with it — re-running `data/seeds/02_channel_capability.sql` after any
downgrade/upgrade round-trip is required to get the capability data back;
this is expected (down-migrations are destructive by design), not a bug.

### 5.2 Seed files (`data/seeds/`, applied in lexical order)

| File | Seeds | Row count (current) |
|---|---|---|
| `01_channels.sql` | 8 channels, 13 escalation-policy rows across 4 severities | 8 + 13 |
| `02_channel_capability.sql` | `channel_capability_tier`, 4 tiers × 8 channels | 32 |
| `03_alert_sources.sql` | 6 alert sources (usgs, gdacs, thunderstorm_nowcast, manual, sachet, imd — last two disabled) | 6 |
| `04_app_config.sql` | every threshold, keyed and noted | 114 |
| `05_relay_nodes.sql` | 6 demo relay nodes — **currently placeholder ciphertext**, real geometry join | 6 (was 0 until §5.4's geometry load) |

`scripts/verify_seeds.py` asserts real counted minimums against the database
after seeding — **not** the design spec's prose numbers, which don't match
what the spec's own SQL produces once you count every `INSERT` tuple.

### 5.3 Known content gaps in the seed data

- `05_relay_nodes.sql` uses dummy `pgp_sym_encrypt('+91PLACEHOLDER...', 'CHANGE-ME')`
  values. Must be redone with real Twilio-verified team phone numbers before
  any human-relay (B9) work is tested. **No longer blocked on geometry** —
  see §5.4, the geometry load is done and this seed now inserts real rows.
- `quality_gate.required_lang_for_severe`/`_extreme` are keyed per state
  (`.KL` → `ml`, `.MH` → `mr`) rather than one global floor, because a single
  `'ml'` requirement would incorrectly gate Palghar (Maharashtra, Marathi)
  alerts.

## 5.4 Geometry load — done, with two more spec corrections found

`scripts/fetch_data.sh` (§3.6's corrections) downloads the raw files;
`scripts/load_admin_units.py`, `load_population.py`, `load_terrain.py`,
`load_safe_zones.py` load them. All pure Python — no GDAL/`ogr2ogr`
dependency, since GDAL is not installed on this machine and installing it on
Windows is its own project. `psycopg` + PostGIS's `ST_GeomFromGeoJSON` does
everything `ogr2ogr` would have. `scripts/run_geometry_pipeline.py`
orchestrates the correct order.

**Current state, locally (Neon copy in progress via `neon-bootstrap` — see §5.6):** `admin_unit`
has 6,822 ADM3 rows (nationwide) + 1,480 ADM5 rows (Wayanad + Palghar), all
8,302 with `population` set. `safe_zone` has 281 real rows from OSM Overpass
(151 hospitals, 84 schools, 32 community centres, 14 other). `relay_node`
has 6 real rows pointing at the correct real containing units.
`unit_features` has terrain ruggedness + mean elevation for 1,375 units —
everything whose footprint overlaps one of the 4 fetched DEM tiles;
everything outside Wayanad/Palghar is correctly `NULL`, not guessed or
zero-filled.

**Two more spec corrections found while loading, beyond §3.6's two:**

1. **geoBoundaries ADM5 files carry no state/ADM1 attribute at all.** The
   design spec's filter (§1.6.2: `-where "shapeGroup='IND' AND ADM1_NAME
   IN ('Kerala','Maharashtra')"`) assumes a column that does not exist —
   confirmed by inspecting an actual feature's properties, which are only
   `shapeName`, `shapeISO` (empty), `shapeID`, `shapeGroup` (always `"IND"`
   for the national extract), `shapeType`. There is no state name anywhere
   in the file. **Fixed:** filter by geometry bounding box instead
   (`load_admin_units.py --bbox south,west,north,east`, repeatable), scoped
   to the two case-study *districts* rather than the two full *states* —
   which is both a tighter scope (matches Trap 4's actual goal better) and
   consistent with how `safe_zone`/`relay_node` are already bbox-scoped to
   the same two districts.

2. **"Wayanad" and "Meppadi" are not distinct shapes at ADM3/ADM5
   resolution.** "Wayanad" is the district name; the design doc's demo
   narrative names "Meppadi" specifically for the relay-node seed, but
   neither exists as a `geoBoundaries` `shapeName` at sub-district/village
   granularity. Confirmed by `ST_Intersects` against Meppadi's real
   coordinates (~11.65°N, 76.13°E): the containing ADM3 unit is
   **"Vythiri"**, the containing ADM5 unit is **"Muttil North"**. Palghar's
   demo town, **"Talasari,"** *does* exist under that exact name at both
   levels — no substitution needed there. `05_relay_nodes.sql` now looks up
   `Muttil North` (level 5) for the Wayanad-side nodes and `Talasari`
   (level 5) for the Palghar-side nodes; the human-readable `name` column on
   each row still says "Meppadi ..." to match the pitch narrative — only the
   geometry join target changed.

**One more operational finding:** the public Overpass API's main instance
(`overpass-api.de`) returned a 504 on the first real query — a known
flakiness with their free public server, not a dead source (confirmed live
in §3.6's check). `load_safe_zones.py` retries once, then falls through to
`overpass.kumi.systems` as a mirror. Worked on the first retry both times.

**A bug in this codebase, not the spec, worth recording the same way:**
`load_terrain.py`'s first version opened all 4 DEM GeoTIFF tiles *inside*
the per-unit loop (`for tile_path in tiles: with rasterio.open(tile_path)`)
— up to ~33,000 file opens for 8,302 units, since every unit outside
Wayanad/Palghar fails against all 4 tiles before being correctly skipped.
It was still running after several minutes and got killed rather than
waited out. Fixed by opening each tile once, before the unit loop, and
reusing the open dataset handles — finished in under 2 minutes afterward.
The lesson generalizes: any per-unit loop that opens a file/connection
inside the loop body is a candidate for this exact mistake, and it's worth
checking for the same pattern before `load_towers.py`'s PostGIS-based
per-unit queries are run at scale (that one uses SQL `CROSS JOIN`, not
per-unit file opens, so it isn't exposed to this specific bug — but it's a
similar shape of risk if this pipeline grows more loaders).

## 5.5 OpenCelliD — the real download shape, and an honest data-coverage gap

§3.6 flagged this as a `SKIP` (no token). With a token, two more things
needed solving, one a URL-shape bug and one a genuine finding about the
data itself.

**The real download URL required reading the page's rendered HTML, not
guessing at REST conventions.** `opencellid.org/downloads` shows a form
(`action="/downloads.php" method="get"`, single field `token`) — submitting
it reveals per-user download links that were never visible in the page
served without a valid token. Those links are:

```
https://opencellid.org/ocid/downloads?token=...&type=full&file=cell_towers.csv.gz
https://opencellid.org/ocid/downloads?token=...&type=diff&file=OCID-diff-cell-export-{date}.csv.gz
```

**Spec correction:** §1.6.2's fetch command
(`type=mcc&file=404.csv.gz`, `type=mcc&file=405.csv.gz`) assumes a
per-country/per-MCC download product that does not exist in the current
API — `type=mcc` doesn't validate; only `full` (one global file) and `diff`
(daily deltas) are real options. There is no server-side country filter
available at all now; filtering has to happen client-side after downloading
the global file. Confirmed: `type=full&file=cell_towers.csv.gz` returns a
real 116MB gzip (`Content-Type: application/gzip`, `Content-Length:
116290903`).

**The honest finding, not a bug:** the global file contains 5,349,901 rows
across 199 distinct MCCs. **Not one of them is MCC 404 or 405 (India).**
OpenCelliD's crowdsourced coverage of India is currently empty in this
export — confirmed by checking every unique MCC value present, not just
filtering and getting zero (which could have been a formatting mismatch;
it wasn't).

`scripts/load_towers.py` handles this as a first-class outcome, not a
failure: if the India row count is zero, it prints exactly that and leaves
`unit_features.tower_count_5km`/`nearest_tower_km` `NULL` for every unit —
which is precisely what makes `v_communication_vulnerability` correctly
report `unknown_connectivity_features_pending` rather than `standard`. Part
30's fallback was written for "the token approval hasn't cleared yet"; it
turns out to be the correct behavior for a different, more permanent reason
too — India tower data isn't there to have. The script is safe to re-run at
any time (rate limit: 2 downloads/day per token) — the dump regenerates
daily, so it will start populating real numbers automatically the day any
India coverage appears, with no code change, matching Part 30's own "strict
feature-set upgrade, no redesign" promise.

The downloaded global file (`data/raw/cell_towers_global.csv.gz`, 116MB) is
gitignored along with the rest of `data/raw/`.

## 5.6 Local vs. Neon — schema matches; geometry bootstrap in progress

Local Docker Postgres and Neon are **not always in the same state**. As of
the last verification:

| | Local (Docker, port 5433) | Neon (`.env.neon`) |
|---|---|---|
| Migrations `0001`–`0012` | ✅ applied, round-tripped | ✅ applied, round-tripped |
| Seed files `01`–`04` | ✅ applied | ✅ applied (112→114 config via upsert) |
| `05_relay_nodes.sql` | ✅ 6 rows (geometry exists) | ⏳ depends on geometry load completing |
| `admin_unit` ADM3+ADM5 | ✅ 8,302 rows | ✅ 8,302 rows (neon-bootstrap verified ADM load) |
| `population` on units | ✅ all ADM3 set | ✅ 6,822/6,822 (neon-bootstrap) |
| `safe_zone` / `unit_features` | ✅ 281 / 1,375 terrain | ⏳ loading via `neon-bootstrap` |
| Consented recipients (CSV) | ✅ ~122 | ❌ run `import-enrollment` after bootstrap |

**Bootstrap commands:**

| Command | What it does |
|---|---|
| `python run.py seed-config` | Idempotent upsert of all `app_config` keys |
| `python run.py data-bootstrap` | Local: migrate + config + enrollment CSV + verify |
| `python run.py neon-bootstrap` | Neon: migrate + config + full geometry pipeline + verify |
| `python run.py verify-data` | Row-count sanity checks (units, config, channels, recipients) |

**`.env.neon` gotcha:** values must **not** be wrapped in quotes — bash
`source` passes quotes literally into `DATABASE_URL`, breaking asyncpg.
`scripts/env_loader.py` strips quotes for Python loads; use unquoted URLs in
the file itself for shell-based tooling.

**Practical consequence:** queries against Neon that join geometry-dependent
views before bootstrap completes return empty — not because views are broken,
but because rows aren't loaded yet.

---

## 8. Application layer — as built (roadmap Day 4–6 slice)

This section tracks **running code**, not the design spec. Updated whenever
a module ships. Last verified: **37/37 pytest green** against local Docker
(Postgres `:5433`, Redis `:6379`).

### 8.1 FastAPI surface (`services/api/`)

| Method | Path | Module | Status |
|---|---|---|---|
| GET | `/health` | `routers/health.py` | ✅ |
| POST | `/api/v1/alerts` | composer create draft | ✅ |
| GET | `/api/v1/alerts` | list (limit from `api.list_default_limit`) | ✅ |
| GET | `/api/v1/alerts/{id}` | alert detail | ✅ |
| POST | `/api/v1/alerts/{id}/preview` | exposure preview | ✅ |
| POST | `/api/v1/alerts/{id}/validate` | F1 quality gate | ✅ |
| POST | `/api/v1/alerts/{id}/approve` | F3 dual authorization | ✅ |
| POST | `/api/v1/alerts/{id}/dispatch` | Delivery fan-out + governance guards | ✅ |
| POST | `/api/v1/alerts/{id}/new-version` | F2 draft vN+1 | ✅ |
| GET | `/api/v1/units/{id}/reachability` | D7f view | ✅ |
| GET | `/api/v1/units/{id}/vulnerability` | D8f view | ✅ |
| GET | `/api/v1/units/{id}/risk` | D12f risk + factors | ✅ |
| GET | `/api/v1/alerts/{id}/assurance` | B8 assurance ladder | ✅ |
| GET | `/api/v1/alerts/{id}/deliveries` | Delivery rows + assurance level | ✅ |
| POST | `/api/v1/ack` | Citizen acknowledgement (idempotent) | ✅ |
| POST | `/api/v1/deliveries/{id}/receipt` | B8 SW receipt (nonce-checked) | ✅ |
| POST | `/api/v1/response` | C6 structured citizen response | ✅ |
| GET | `/api/v1/assistance` | D11f queue (priority-ordered) | ✅ |
| GET | `/api/v1/assistance/{id}` | D11f case detail + factors | ✅ |
| POST | `/api/v1/assistance/{id}/assign` | D11f assignment | ✅ |
| GET | `/api/v1/incidents/{id}` | F2 version chain | ✅ |
| GET | `/api/v1/incidents/{id}/timeline` | D10f audit timeline | ✅ |
| GET | `/api/v1/public/config` | PWA + citizen runtime keys | ✅ |
| GET | `/api/v1/public/signing-key` | Ed25519 public key (b64) | ✅ |
| GET | `/api/v1/citizen/deliveries/{id}` | Offline-capable alert payload | ✅ |
| POST | `/api/v1/admin/recipients/import` | E4 CSV enrollment | ✅ |
| POST | `/webhooks/sms-inbound` | SMS keyword REGISTER/STOP | ✅ |
| POST | `/webhooks/sms-status` | Twilio delivery status | ✅ |
| POST | `/webhooks/ivr-status` | IVR DTMF → citizen response | ✅ |

CORS allows `http://localhost:5173` for citizen PWA dev (`services/api/main.py`).

**Env-gated live channels:** FCM, SMS, IVR, email adapters send for real when
credentials are present; otherwise worker catches `ChannelUnavailable` and
uses `SimulatedCarrierAdapter`. Firebase/Twilio/Brevo still blocked for most
deployments — sim path is honest, not silent.

**Not wired yet:** B10 peer relay receipt, B9 full human-relay call flow,
PDF audit report, officer console UI, E1 RBAC on mutating routes.

**Process entry points** (via `python run.py …`):

| Task | Module |
|---|---|
| `api` | `uvicorn services.api.main:app` |
| `worker` | `services.delivery.worker` (Redis Streams consumer) |
| `ingest` | `services.ingestion.scheduler` (USGS + GDACS pollers) |
| `seed-config` | `scripts/upsert_app_config.py` (idempotent config refresh) |
| `data-bootstrap` | `scripts/bootstrap_local_data.py` |
| `neon-bootstrap` | `scripts/bootstrap_neon.py` |
| `neon-geometry` | `scripts/push_geometry_to_neon.py` |
| `import-enrollment` | `scripts/import_enrollment_csv.py` |
| `verify-data` | `scripts/verify_data_layer.py` |
| `citizen-dev` | Vite dev server `:5173` |

### 8.2 Ingestion (`services/ingestion/`)

- **`UsgsAdapter`** — zero-auth GeoJSON; magnitude→severity from
  `ingest.usgs.mag_*` config keys; `estimated_onset_at` always NULL
  (earthquakes have no forecast lead time — by physics, not omission).
- **`GdacsAdapter`** — uses `/geteventlist/SEARCH`, **not** `/MAP`
  (the spec's MAP endpoint 400s without `eventtype`; fixed in
  `data/seeds/03_alert_sources.sql`).
- **`poller.py` / `scheduler.py`** — APScheduler loop; quarantine on
  parse/HTTP failures; incident auto-open on first sighting.
- **`incident_linker.py`** — links ingested events to open incidents /
  creates new incident rows before persist.
- **Fixtures:** `tests/fixtures/usgs_feature.json`, `gdacs_search.json`.

### 8.3 Delivery engine (`services/delivery/`)

- **`state_machine.py`** — 8-state transactional lifecycle with
  `FOR UPDATE` transitions and audit append.
- **`assurance.py`** — append-only `delivery_event` writer;
  `acknowledged` tier also calls `transition(state=acknowledged)`.
  Metadata stored as JSON string for asyncpg jsonb compatibility.
- **`engine.py`** — dispatch path: approvals → quality gate →
  **F2 supersede** (if `supersedes_alert_id` set) → create deliveries →
  Redis `XADD` fan-out. Redis `SET NX PX` supersede lock per incident
  (`versioning.supersede_lock_ms`).
- **`worker.py`** — consumer group; real adapters when creds present;
  `ChannelUnavailable` → honest sim fallback (not silent success).
- **Channel adapters:** `SimulatedCarrierAdapter` always available;
  `FcmAdapter`, `SmsAdapter`, `IvrAdapter`, `EmailAdapter` are real
  when env creds exist; siren/human_relay/community_relay remain stubs
  pending hardware/Twilio/B10 spike.

### 8.4 Governance (`services/governance/`)

- **`quality_gate.py`** — all **6/6 F1 rules** live:
  `geometry_non_empty`, `expiry_set`, `target_count_plausible`,
  `escalation_policy_exists`, `translation_exists`, `target_area_plausible`.
  Translation requirement is **state-keyed** via `case_study.bbox.KL` /
  `.MH` and `quality_gate.required_lang_for_{severity}.{state}` — a single
  global `'ml'` floor would incorrectly block Palghar (Marathi) alerts.
  `target_area_plausible` returns **`warn`**, not `fail`, above
  `quality_gate.max_target_area_km2`.
- **`approvals.py`** — quorum by severity; `authoritative_source`
  auto-approval for `is_authoritative` feeds (USGS/GDACS).
- **`versioning.py`** — `create_new_version()` drafts vN+1;
  `supersede_predecessor()` on dispatch marks old version `superseded` and
  expires `pending`/`queued` deliveries when
  `versioning.cancel_inflight_on_supersede=true`.

### 8.5 Citizen response, enrollment & assistance (C6 + E4 + D11f)

- **`citizen_response.py`** — idempotent `POST /response` handler;
  `CHECK (location IS NULL OR location_consent=true)` enforced at DB;
  writes `delivery_event` tier `citizen_response`; emits
  `citizen.response_received` audit event. Free-text cap from
  `response.free_text_max_chars`.
- **`assistance_queue.py`** — auto-opens `assistance_case` for
  `trapped|medical|unable_to_evacuate|other`; priority from
  `priority.py` weighted sum (Rule 10 — full factors stored in
  `priority_factors` JSONB). List limit from `api.list_default_limit`.
- **`services/enrollment/`** — `phone_hash.py` (HMAC dedupe),
  `csv_import.py` (dry-run → preview_token → live), `sms_keyword.py`
  (REGISTER/STOP with rate limit from config).
- Proximity normalisation uses `assistance.proximity_max_m` against
  unit centroid or consented citizen point.

### 8.6 Audit timeline (D10f)

- **`audit/ledger.py`** — hash-chained append-only events.
- **`audit/timeline.py`** — `GET /incidents/{id}/timeline` is a straight
  `SELECT … ORDER BY occurred_at` — no second log, no materialised view.

### 8.7 CI & quality gates

- **`.github/workflows/ci.yml`** — PostGIS + Redis services, migrate,
  seed, ruff, `check_no_hardcoding.py`, `check_pwa_config.py`,
  `check_env_example.py`, `check_channel_capability.py`, unit + property tests.
- **`scripts/upsert_app_config.py`** — parses `04_app_config.sql` and
  upserts all keys (`ON CONFLICT DO UPDATE`) so config can be refreshed
  without wiping channels/sources on an existing DB.
- **Re-seed note:** `python run.py seed` still fails on duplicate
  `channel` rows if the DB already has data; use `seed-config` for
  config-only refresh, or `db-reset` for a clean slate.

### 8.8 Config keys added beyond Part 21 prose

| Key | Why |
|---|---|
| `ingest.*`, `delivery.xread_*`, `geo.km_to_meters` | Ingestion poller + worker tuning |
| `case_study.bbox.KL` / `.MH` | F1 translation rule — south,west,north,east order |
| `assistance.proximity_max_m` | D11f proximity factor normalisation |
| `response.free_text_max_chars` | C6 Pydantic cap + PWA textarea maxLength |
| `pwa.*` | Service worker NetworkFirst timeout + cache + BackgroundSync retention |
| `api.idempotency_ttl_seconds` | Dispatch idempotency replay window |
| `api.version_conflict_retry_after_ms` | Retry-After when supersede lock held |
| `api.list_default_limit` | Default pagination when `?limit=` omitted |
| `geometry.admin_unit_batch_size` | Loader INSERT batch size |
| `assistance.default_vulnerability` | Fallback when terrain feature NULL |
| `risk.top_factors_limit` | Cap on risk factor rows returned |
| `alert.manual.default_radius_km` | Point-alert buffer when no polygon |
| `enrollment.*` | CSV caps, phone digit lengths, SMS keywords/replies |
| `ivr.dtmf.*`, `ivr.prompt.main` | Twilio Gather prompts and digit map |

### 8.9 Hardcoding policy — what's allowed where

**Rule:** operational thresholds, timeouts, caps, and policy defaults live
in `app_config` (seeded by `04_app_config.sql`, refreshed via
`python run.py seed-config`). Code reads them through `config_repo` (async
API) or `scripts/db_config_sync.py` (sync loaders).

**CI enforcement:**

| Guard | Scope |
|---|---|
| `scripts/check_no_hardcoding.py` | `services/delivery`, `targeting`, `governance`, `response`, `enrollment`, `ingestion` — flags bare numeric literals in `Compare`/`BinOp` except `{0,1,-1,2,100}` and subscripts |
| `scripts/check_pwa_config.py` | `web/citizen/src` — flags hardcoded PWA timeouts and `freeTextMax` defaults |
| `scripts/check_channel_capability.py` | Adapter tier flags vs `channel_capability_tier` table |

**Explicit exceptions (not bugs):**

- **HTTP status codes** in `HTTPException(status_code=…)` — protocol constants.
- **Bootstrap geometry scripts** — `load_terrain.py`'s `RUGGEDNESS_STD_CEILING_M`
  is a *units-of-measurement* choice for the std-dev proxy, documented in-file;
  the *policy* threshold is `vuln.terrain_ruggedness_ceiling` in `app_config`.
- **Dev-only Vite proxy** — `vite.config.ts` `localhost:8000` for local API;
  production builds use same-origin or env-based `apiBase()`.
- **Test fixtures** — synthetic coordinates and buffers in `tests/`.
- **SQL positional placeholders** — `$1`, `$4` in queries are not literals.

**Citizen PWA:** service worker registers API caching routes only after
`GET /api/v1/public/config` succeeds — no in-code fallback for
`pwa.network_timeout_seconds` etc. App UI waits for config before enabling
free-text `maxLength`.

## 8.1 Five bugs a green test suite did not catch

All 37 tests passed while live ingestion was completely broken. Every bug
below was found by running the real system against the real database and the
real feeds — not by reading code and not by running tests. Recorded because
the *pattern* generalises, not just the fixes.

**1. asyncpg returns `jsonb` as `str`, not `dict`.**
`load_adapters()` did `dict(row["config"])` on `alert_source.config` and
raised `dictionary update sequence element #0 has length 1; 2 is required`
against the real DB. Fixture-based tests never saw it: they construct config
dicts in Python, so the value never crosses the driver boundary. Fixed by
registering a json/jsonb codec **centrally** in `services/api/db.py::connect()`
— this affects every jsonb column in the schema (`channel.config`,
`assistance_case.priority_factors` (Rule 10's stored inputs),
`delivery_event.metadata`, `reach_prediction.features`), so fixing it at one
call site would have left four others silently broken. `deps.py` and
`tests/conftest.py` both now route through `connect()`, so **tests use the
same connection path as production** — the divergence is what hid the bug.

**2. Shared HTTP policy was never passed to adapters.**
`ingest.http_timeout_s` / `ingest.http_not_modified_status` were correctly
seeded in `app_config` (they are system-wide policy, not per-feed config) but
the registry never injected them, so every adapter raised
`missing 2 required positional arguments`. The registry now merges them in and
filters by each adapter's actual `__init__` signature.

**3. `alert_source` seed was not idempotent.**
It used a bare `INSERT`, so re-running could never *correct* a drifted row.
The database held a stale gdacs config pointing at `.../geteventlist/MAP`
(which returns 400 `Eventtype is required`) while the seed file already had
the correct `/SEARCH` URL. Now `ON CONFLICT (source_id) DO UPDATE` — a seed
file that is the source of truth (Rule 3) must be able to repair drift.

**4. `admin_unit.state_code` does not exist.**
`incident_linker.generate_label()` queried `COALESCE(u.state_code, u.name)`.
That column has never existed in any migration, so live USGS ingestion died
with `UndefinedColumnError` — while unit tests, which never exercise labeling
against a real schema, passed. Fixed to `ORDER BY u.level ASC` (prefer the
coarser ADM3 sub-district over an ADM5 village), which recovers the intended
"name it after the wider region" behaviour without the phantom column.

**5. One broken adapter took down the entire registry.**
`thunderstorm_nowcast` and `manual` were seeded `enabled=true` with no adapter
module, so a `ModuleNotFoundError` on one killed the registry for *all*
sources, including working ones. Two fixes: the registry now logs and skips an
unbuildable adapter instead of raising, and the seed marks both rows
`enabled=false` — `manual` is a **provenance, not a feed** (officer-composed
alerts arrive via the composer API, never by polling), so it should never have
been pollable at all.

**Two further Rule-1 violations found in the same pass**, both invisible to
the existing guard:

- `services/api/routers/webhooks.py` hardcoded `gather_digits="1"`,
  `gather_timeout="10"` as function defaults, silently ignoring the seeded
  `ivr.gather_digits` / `ivr.gather_timeout_s` rows (the spec's own Part 38
  violation E, reintroduced). `check_no_hardcoding.py` could not see it for
  two reasons — it did not guard `services/api/`, and it only inspected
  `Compare`/`BinOp` nodes, so a *default argument* was invisible. Both gaps
  are now closed, and the strengthened guard was verified to actually fail on
  a probe file reproducing the exact pattern before being trusted.
- `PeerRelayAdapter` declared `supports_device_delivered=False` /
  `supports_opened=False`, contradicting its seeded `channel_capability_tier`
  rows. That is a **Rule 8 violation** — the product's central honesty claim —
  caught by `check_channel_capability.py`, which is precisely why that guard
  exists.

**The generalisable lesson:** every one of these lived at a boundary the tests
mocked away — the DB driver, the config table, the seed file, the live HTTP
feed. Tests that construct their own inputs cannot catch a bug in how real
inputs arrive. That is the argument for the integration run the roadmap
requires, and for `conftest.py` using the production connection path.

---

## 6. Open engineering questions

### 6.1 Community Relay Mode (B10) — Web Bluetooth role limitation

`shareNearby()` as designed calls `navigator.bluetooth.requestDevice()` and
connects as a GATT **client**. No shipping browser exposes the GATT
**peripheral/server** role to a web page — meaning Device A cannot advertise
a service for Device B to discover and write to. Phone-to-phone relay
through two PWA tabs, as specced, may not be achievable in a browser at all
(as opposed to being merely rate-limited by the user-gesture requirement,
which is a real but separate constraint).

**Not yet spiked.** Needs ~20 minutes with two Android phones + Chrome
DevTools to confirm one way or the other before any code is written against
it. If confirmed impossible as a two-PWA browser feature, the fallback is
either: (a) drop to a native wrapper for just this feature, or (b) cut it —
it's already a standalone, non-load-bearing feature per the design doc.
The Ed25519 signing/verification work is worth keeping regardless of this
outcome — it's reused for verifying the FCM push payload too.

### 6.2 ML service hosting

Not yet decided or built. Needs an isolated deployment target that never
loads inside the API process (§3.1's hard rule).

### 6.3 Neon / cloud database

Neon is **set up and migration-verified** (§5.6). Full geometry bootstrap
runs via `python run.py neon-bootstrap` (`.env.neon`). As of last check:
ADM3 (6,822) + ADM5 (1,480) + population loaded; terrain/safe zones/verify
may still be running on long jobs. Re-run `python run.py verify-data` with
`SETU_ENV_FILE=.env.neon` after bootstrap completes.

---

## 7. Repository layout

```
setu/
├── CLAUDE.md            binding project rules
├── TASK.md              status-based task tracker — "what do I do next"
├── services/
│   ├── api/             main.py, deps.py, schemas.py, config_repo.py, db.py
│   │   └── routers/     alerts, health, units, response, assistance, incidents,
│   │                    public, citizen, enrollment, webhooks, ack, receipts
│   ├── delivery/        engine, state_machine, assurance, worker, keys
│   │   └── channels/    base + simulated + fcm/sms/ivr/email (env-gated) + stubs
│   ├── ingestion/       usgs/gdacs adapters, poller, scheduler, normalize, persist, incident_linker
│   ├── governance/      quality_gate (6/6), approvals, versioning, composer
│   ├── response/        citizen_response, assistance_queue, priority
│   ├── enrollment/      phone_hash, csv_import, sms_keyword
│   ├── targeting/       geo.py, escalation.py
│   ├── audit/           ledger.py, timeline.py
│   ├── crypto/          alert_signing.py (Ed25519 — server side)
│   └── ml/              (not started — hosting TBD)
├── web/
│   ├── console/src/     (empty — React ops console)
│   └── citizen/         PWA — Vite + React + Workbox (src/sw.ts)
├── data/seeds/          01–05 applied locally
├── migrations/          0001–0012 applied locally + Neon (schema)
├── tests/               unit/ + property/ + fixtures/ — 37 tests green
├── scripts/             bootstrap, CI guards, geometry pipeline, upsert_app_config, db_config_sync
├── infra/               docker-compose.yml (Postgres :5433, Redis, MailHog)
├── .github/workflows/   ci.yml
├── run.py               task runner (Makefile replacement)
└── docs/                SETU_MASTER (spec), IMPLEMENTATION.md (this file), TASK.md
```
