# SETU — Implementation Reference

This is the living technical reference for what's actually built, how it's built,
and why. It is derived from `docs/SETU_MASTER_v3.0_MERGED.md` (the design spec)
but is **not a copy of it** — this doc tracks reality: what deviates from the
spec, what was fixed, what's still open, and the concepts underneath the code.

When the spec and this doc disagree, **this doc wins** — it reflects what's
actually running. Update it in the same commit as the code change it describes.

Latest application reality: **§6.18** (22 Aug SIH live Extreme on Neon),
**§7.6** (officer desk: Help needed vs Send a runner), **§7.7**
(citizen session persistence + sideload APK), **§10** (deploy runbook),
**§10.5** (presenting device + how to show unrehearsed beats), **§11**
(Part 19 Definition of Done walk), **§12** (dated evidence logs).
For "what to do next," see `docs/TASK.md`. This file is "how does it work
and why," not "what's left." The only other binding docs are
`docs/SETU_MASTER_v3.0_MERGED.md` (spec) and `docs/TASK.md` (status).

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

### 3.4 Frontend — both apps shipped

Full detail in §7; this is the stack summary only.

| App | Path | Stack | Status |
|---|---|---|---|
| Citizen PWA | `web/citizen/` | Vite + React 19 + Workbox | ✅ MVP — offline-capable |
| Officer console | `web/console/` | Vite + React 19 + lucide-react | ✅ 3 of 5 event-time screens (§7.3) |

The two apps share **no** styling or components. Part 0.4's governing
decision is that they invert on almost every axis (dark/light, dense/sparse,
keyboard/thumb, network-present/network-absent), so the three components that
appear in both are designed twice rather than shared.

**Citizen PWA (`web/citizen/`):** light-first alert viewer and C6 response
flow (18px body, 44px targets, `theme-color` `#f4f6f8`). All runtime tuning
(PWA cache timeouts, BackgroundSync retention, `response.free_text_max_chars`,
help types and labels) comes from `GET /api/v1/public/config` — no hardcoded
fallbacks in `App.tsx` or `sw.ts` (enforced by `scripts/check_pwa_config.py`
in CI). Ed25519 verify key from env
(`VITE_ALERT_SIGNING_PUBKEY_B64`) or `GET /api/v1/public/signing-key`.
Push notifications require Firebase + VAPID. Live `fcm_send`
`provider_accepted` is proven on alert 6 (§6.18) for Muttil recipients
1, 3, and 4; recipient 5’s token was `device_unregistered` (honest fail).
Citizen access/refresh tokens live in **`localStorage`**, not
`sessionStorage` — a WebView / installed PWA that stored the session in
`sessionStorage` logged the resident out on every process death (§7.7).
After sign-in the PWA loads `GET /api/v1/citizen/deliveries` for the
account's enrolled village — there is no typed delivery ID (§6.16). Dev
server proxies `/api` → `localhost:8000` in `vite.config.ts` only — not a
production config path. Live: `https://setucitizen.vercel.app` (`:5174`
locally). Sideload APK: `python run.py citizen-apk` →
`mobile/citizen-apk/dist/SETU-citizen.apk` (WebView of that origin, not
Play Store).

**Officer console:** dark-first ops UI — Live Operations, Compose, Alert
Detail, Assistance, Incident, Command Board, Methodology, Analytics, Relay,
Enrollment. Copy is plain officer language in **en / hi / ml / mr**
(`web/console/src/lib/i18n.tsx`). Live: `https://setuconsole.vercel.app`
(`:5173` locally).

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
| `0013_auth` | `app_user.password_hash`/`last_login_at`; `refresh_token` (revocable sessions); `audit_event(actor)` index for the contact-reveal audit query (§6.10) | ✅ |

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
| `04_app_config.sql` | every threshold, keyed and noted | 131 |
| `05_relay_nodes.sql` | 6 demo relay nodes — **currently placeholder ciphertext**, real geometry join | 6 (was 0 until §5.4's geometry load) |
| `06_app_users.sql` | all six Part 26 roles, `password_hash` **NULL** — "cannot log in", never "any password works" (§6.10) | 6 |

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
| Seed files `01`–`04` | ✅ applied | ✅ applied (config via idempotent upsert) |
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

## 6. Application layer — as built

This section tracks **running code**, not the design spec. Updated whenever
a module ships. Last verified 21 Aug 2026: **267 passed, 2 skipped**,
`services/delivery` coverage **95.87%** against local Docker
(Postgres `:5433`, Redis `:6379`), with all six guard scripts and
`ruff check services/` green. Live-provider status: **Twilio SMS proven end to
end** (real `provider_accepted` → real carrier callback → `device_delivered`);
Firebase credential authenticates but no token has been minted yet, so
`delivery_event` still holds zero rows with `source='fcm_send'`. **Deployed**
to Vercel + Render + Neon + Upstash at ₹0 (§6.14); Part 19's Redis-budget and
DEM boxes closed with real measurements, and a citizen-facing bug the deploy
surfaced is fixed (§6.15). See §6.13 for what the original audit found.

### 6.1 FastAPI surface (`services/api/`)

| Method | Path | Module | Status |
|---|---|---|---|
| GET | `/health` | `routers/health.py` | ✅ |
| POST | `/api/v1/alerts` | composer create draft | ✅ |
| GET | `/api/v1/alerts` | list (`lifecycle_status`, `severity`, `source_id`, `authoritative`; limit from `api.list_default_limit`) | ✅ |
| GET | `/api/v1/alerts/{id}` | alert detail | ✅ |
| POST | `/api/v1/alerts/{id}/preview` | exposure preview | ✅ |
| POST | `/api/v1/alerts/{id}/validate` | F1 quality gate | ✅ |
| POST | `/api/v1/alerts/{id}/approve` | F3 dual authorization | ✅ |
| POST | `/api/v1/alerts/{id}/dispatch` | Delivery fan-out + governance guards | ✅ |
| POST | `/api/v1/alerts/{id}/new-version` | F2 draft vN+1 | ✅ |
| GET | `/api/v1/units/{id}/reachability` | D7f view | ✅ |
| GET | `/api/v1/units/{id}/vulnerability` | D8f view | ✅ |
| GET | `/api/v1/units/{id}/risk` | D12f risk + factors | ✅ |
| GET | `/api/v1/ops/map` | D1f GeoJSON units (+ unused alert FC); officer envelope + finest level + geom clip | ✅ |
| GET | `/api/v1/ops/summary` | Live Ops KPI strip | ✅ |
| GET | `/api/v1/ops/feed` | Delivery-event kill feed | ✅ |
| GET | `/api/v1/alerts/{id}/assurance` | B8 assurance ladder | ✅ |
| GET | `/api/v1/alerts/{id}/deliveries` | Delivery rows + assurance level | ✅ |
| POST | `/api/v1/ack` | Citizen acknowledgement (idempotent) | ✅ |
| POST | `/api/v1/deliveries/{id}/receipt` | B8 SW receipt (nonce-checked) | ✅ |
| POST | `/api/v1/response` | C6 structured citizen response | ✅ |
| GET | `/api/v1/assistance` | D11f queue (officer full; auditor stripped) | ✅ |
| GET | `/api/v1/assistance/summary` | §12.2 count + area (relay_node allowed) | ✅ |
| GET | `/api/v1/assistance/{id}` | D11f case detail + factors | ✅ |
| POST | `/api/v1/assistance/{id}/assign` | D11f assignment | ✅ |
| GET | `/api/v1/incidents/{id}` | F2 version chain | ✅ |
| GET | `/api/v1/incidents/{id}/timeline` | D10f audit timeline | ✅ |
| GET | `/api/v1/public/config` | PWA + citizen runtime keys | ✅ |
| GET | `/api/v1/public/signing-key` | Ed25519 public key (b64) | ✅ |
| GET | `/api/v1/citizen/deliveries` | Active warnings for the session's enrolled unit | ✅ |
| GET | `/api/v1/citizen/deliveries/{id}` | Offline-capable alert payload | ✅ |
| POST | `/api/v1/admin/recipients/import` | E4 CSV enrollment | ✅ |
| POST | `/webhooks/sms-inbound` | SMS keyword REGISTER/STOP | ✅ |
| POST | `/webhooks/sms-status` | Twilio delivery status | ✅ |
| POST | `/webhooks/ivr-status` | IVR DTMF → citizen response | ✅ |

CORS allows `http://localhost:5173` / `:5174` (console and citizen) in
`services/api/main.py` by default. Deployed origins
(`https://setucitizen.vercel.app`, `https://setuconsole.vercel.app`) are
added via Render `CORS_ALLOWED_ORIGINS` — never hardcoded in `main.py`.
Dev still prefers the Vite same-origin proxy.

**Env-gated live channels:** FCM, SMS, IVR, email adapters send for real when
credentials are present; otherwise worker catches `ChannelUnavailable` and
uses `SimulatedCarrierAdapter`. Firebase/Twilio/Brevo still blocked for most
deployments — sim path is honest, not silent.

**Still external, not missing code:** FCM/SMS/IVR `provider_accepted` are proven on live Extreme alert 6 (§6.18). Remaining: SW `service_worker` receipt on the presenting phone, Gate 3 airplane-mode reopen (§10.5), B9 runner confirm via `ivr_dtmf` (HTTP confirm exists), HF Space host. B10 GATT peripheral is impossible in a browser; the demo path is a signed `?peer=` URL (§8.1, §10.5). Gate 3 has a committed Protomaps extract (`python run.py fetch-basemap`, earth/water/roads, India bbox `68,6,98,38`, maxzoom **6**, ~2.6 MB). Spec still asks for Wayanad+Palghar z12. IndicTrans2 still needs an HF Space — the API only caches over HTTP; `services.ml.server` loads weights only when `SETU_LOAD_ML_MODELS=1`.

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
| `citizen-dev` | Vite dev server `:5174` |
| `snapshot` | `scripts/snapshot.py` |
| `fetch-basemap` | `scripts/fetch_basemap.py` (go-pmtiles extract, placeholder fallback) |
| `demo` | `scripts/guard_local_only.py` → migrate → snapshot load/verify |

### 6.2 Ingestion (`services/ingestion/`)

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

### 6.3 Delivery engine (`services/delivery/`)

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
  `ChannelUnavailable` → honest sim fallback (not silent success), except
  FCM `device_unregistered` which must **fail**, never simulate a push.
  Extreme Send inserts SMS + IVR for every numbered phone and FCM when a
  token exists; `process_recipient` sends **every** pending/queued row for
  that person, not `LIMIT 1`. See §6.18.
  Drains due retries every loop tick, **including the idle one** — the
  `XREADGROUP` block window is the natural pacing, and draining only when the
  stream had traffic would mean a retry scheduled during a quiet period never
  fired.
- **`retry.py` (B3)** — policy-driven retry and channel escalation. See §6.13:
  this was the largest gap in the build and the four policy columns were dead
  for the entire project until 21 Aug.
- **Channel adapters:** `SimulatedCarrierAdapter` always available;
  `FcmAdapter`, `SmsAdapter`, `IvrAdapter`, `EmailAdapter` are real
  when env creds exist; `HumanRelayAdapter` places a real Twilio call to
  the registered runner when Twilio is configured. Siren still has no
  digital receipt. Community relay (B10) is still the Web Bluetooth spike.

### 6.4 Governance (`services/governance/`)

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

### 6.5 Citizen response, enrollment & assistance (C6 + E4 + D11f)

- **`citizen_response.py`** — idempotent `POST /response` handler;
  `CHECK (location IS NULL OR location_consent=true)` enforced at DB;
  writes `delivery_event` tier `citizen_response`; emits
  `citizen.response_received` audit event. Allowed types from
  `response.help_types` + `response.safe_type`; free-text types from
  `response.free_text_types`; cap from `response.free_text_max_chars`.
- **`assistance_queue.py`** — auto-opens `assistance_case` for every type
  in `response.help_types` (`trapped`, `medical`, `unable_to_evacuate`,
  `other`); **SAFE does not open a case**. Priority from
  `priority.py` weighted sum (Rule 10 — full factors stored in
  `priority_factors` JSONB). List limit from `api.list_default_limit`.
  Officer list/summary scope is the same geographic rule as
  `assert_unit_in_scope` (parent tree **or** `ST_Intersects`), because
  every `admin_unit.parent_id` is NULL — see §6.18.
- **Ack is not a reply.** `POST /ack` writes `delivery_event.acknowledged`
  and may move `delivery.state`. Only `citizen_response` (SMS SAFE/HELP,
  IVR DTMF, or PWA Safe/Help) is a human answer. Help needed reads
  `assistance_case`, not acks.
- **`services/enrollment/`** — `phone_hash.py` (HMAC dedupe),
  `csv_import.py` (dry-run → preview_token → live), `sms_keyword.py`
  (REGISTER/STOP with rate limit from config).
- Proximity normalisation uses `assistance.proximity_max_m` against
  unit centroid or consented citizen point.

### 6.6 Audit timeline (D10f)

- **`audit/ledger.py`** — hash-chained append-only events.
- **`audit/timeline.py`** — `GET /incidents/{id}/timeline` is a straight
  `SELECT … ORDER BY occurred_at` — no second log, no materialised view.

### 6.7 CI & quality gates

- **`.github/workflows/ci.yml`** — PostGIS + Redis services, migrate,
  seed, ruff, `check_no_hardcoding.py`, `check_pwa_config.py`,
  `check_env_example.py`, `check_channel_capability.py`, unit + property tests.
- **`scripts/upsert_app_config.py`** — parses `04_app_config.sql` and
  upserts all keys (`ON CONFLICT DO UPDATE`) so config can be refreshed
  without wiping channels/sources on an existing DB.
- **Re-seed note:** `python run.py seed` still fails on duplicate
  `channel` rows if the DB already has data; use `seed-config` for
  config-only refresh, or `db-reset` for a clean slate.

### 6.8 Config keys added beyond Part 21 prose

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
| `response.help_types` / `response.safe_type` / `response.free_text_types` / `response.location_prompt_types` / `response.label.*` | C6 choices and copy — PWA and queue render from these |
| `response.geolocation_timeout_ms` | Browser GPS wait when a location-prompt type is tapped |
| `api.deliveries_list_limit` / `ui.ladder_extra_sample` | Alert Detail delivery list + extra ladders after one-per-channel |

### 6.9 Hardcoding policy — what's allowed where

**Rule:** operational thresholds, timeouts, caps, and policy defaults live
in `app_config` (seeded by `04_app_config.sql`, refreshed via
`python run.py seed-config`). Code reads them through `config_repo` (async
API) or `scripts/db_config_sync.py` (sync loaders).

**CI enforcement:**

| Guard | Scope |
|---|---|
| `scripts/check_no_hardcoding.py` | Python AST in `services/{delivery,targeting,governance,response,enrollment,ingestion,api,ml}`; SQL VIEW comparisons in `data/seeds` + `migrations`; TS comparisons in `relay.ts` / `verify.ts` / `response.ts` / `sw.ts`. Allowlist `{0,1,-1,2,100}` (SQL also 4326). TwiML covered by `tests/unit/test_twiml_has_no_literals.py` |
| `scripts/check_pwa_config.py` | `web/citizen` — flags hardcoded PWA timeouts, C6 `HELP_TYPES`, dark `#0f172a` theme |
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
free-text `maxLength`, C6 choice buttons, and geolocation timeout.

### 6.10 Authentication and RBAC (Part 26)

Until migration `0013`, **every one of the API's 29 endpoints was
unauthenticated** — including `POST /alerts/{id}/dispatch`, which fans an
alert out to every consented recipient. On a system that can order an
evacuation, that is the single worst defect available, and it also made every
governance guarantee in the platform unverifiable:

- `POST /alerts/{id}/approve` took **`approver_id` from the request body**.
  `UNIQUE (alert_id, approver_id)` is a real database guarantee, but it
  guarantees nothing about *identity* if the caller declares who they are —
  F3's Four-Eyes quorum was bypassable by typing a different integer.
- The audit ledger's `actor` was a caller-supplied string (`"api"` for every
  dispatch). "Who ordered this evacuation" had no answer.
- §12.2's privacy design — relay_node never sees assistance cases, auditor
  gets aggregate-only — has no runtime meaning without a role on the request.

### What was built

| Piece | Decision, and why |
|---|---|
| **Access token** | Stateless JWT, short TTL from `jwt.access_ttl_minutes`. Stateless means *un-revocable*, so the TTL **is** the revocation window — hence short. |
| **Refresh token** | **Opaque random string, stored server-side as a SHA-256 hash, rotated on every use.** Not a JWT: a system that can order an evacuation must be able to cut off a stolen credential, and a stateless refresh token cannot be revoked. |
| **Theft detection** | Presenting an already-consumed refresh token revokes the **entire family**, not just that token. Replay and race are indistinguishable from the server's side, so both are treated as compromise. Verified live: after a replay, the legitimately-rotated token is also dead. |
| **Password storage** | bcrypt, cost from `auth.bcrypt_rounds`. |
| **No self-registration** | Officer/admin/auditor/relay accounts are provisioned by an administrator. An open sign-up endpoint on this system would be indefensible. Citizen enrollment (E4) creates `recipient` rows, not logins. |

### Three details that are easy to get wrong

**passlib was dropped, not pinned around.** passlib 1.7.4 (last release 2020)
is incompatible with bcrypt 5.x — it raises *"password cannot be longer than
72 bytes"* from its own internal self-test. Pinning an old bcrypt to keep an
unmaintained wrapper alive is the wrong trade on a security-critical path, and
the wrapper was not handling the 72-byte limit for us anyway.

**bcrypt's 72-byte limit is handled explicitly, not by truncation.** bcrypt
ignores everything past 72 bytes, so two different long passwords sharing a
72-byte prefix would be *interchangeable*. Passwords are SHA-256'd and
base64-encoded first, giving a fixed 44-byte input: no user-facing length cap,
nothing silently truncated. base64 (not the raw digest) matters — a raw digest
can contain a NUL byte, which C-string handling inside bcrypt treats as
end-of-input. There is a test asserting the prefix-collision case.

**Login failures are uniform.** Unknown account, no credential set, wrong
password, and deactivated account all return the same 401 with the same code,
and `verify_password` burns a real bcrypt comparison against a dummy hash when
no credential is stored — otherwise login *latency* reveals which accounts
exist and are provisioned.

### Seed accounts

`data/seeds/06_app_users.sql` creates all six Part 26 roles with
`password_hash = NULL`, which means **"cannot log in"** — never "any password
works". Committing the file therefore creates no usable credential; passwords
are set out of band with `scripts/set_password.py`, which reads from a hidden
prompt (never argv, which would land in `ps` output and shell history).

The seed domain is `@setu.example`, not `@setu.local`: `.local` is
IANA-reserved for mDNS and is correctly rejected by `EmailStr`, while
`.example` is reserved by RFC 2606 precisely so a stray address can never
reach a real person.

> **Migration note.** The original accounts were seeded at `@setu.local` and
> could not be deleted once they had approval history — `alert_approval`
> references them, and that history is part of the immutable audit record.
> They were **deactivated** rather than removed, so past approvals stay
> attributable while the accounts can no longer authenticate. Deleting
> audit-referenced users is not something this system should make easy.

### Verified, live

Dispatch went from **200 with no token** to **401**; citizen and auditor
tokens get **403**; a spoofed `approver_id` is **422** (rejected outright, via
`model_config = {"extra": "forbid"}`, rather than silently ignored). 29 RBAC
tests cover Part 26's matrix allow-and-deny per role, plus signature
tampering and a role-escalation attempt that rewrites `role` in the JWT
payload.

### Unit scope at provision time

`services/api/rbac.py` provides `assert_unit_in_scope` /
`assert_alert_in_scope`, wired into the alert write path **and** unit
read path (`/units/{id}/reachability|vulnerability|risk`). Seed SQL still
leaves `unit_scope_id` NULL because `admin_unit` ids are `BIGSERIAL`.
`python run.py provision-demo` (also run at the end of `python run.py demo`)
assigns scopes by ILIKE name lookup from `demo.unit_scope.<email>` in
`app_config`. Both demo officers share **Vythiri** (ADM3, id 3081) so
Four-Eyes can approve the same alert. Citizen and relay use **Muttil North**
(ADM5, id 8157 — the village that contains Meppadi). `state_admin` and
`auditor` stay unscoped. geoBoundaries has no row named Wayanad.

**`parent_id` is unused.** Every one of the 8,302 `admin_unit` rows has
`parent_id IS NULL` — geoBoundaries ADM3 and ADM5 were loaded as two
independent layers, with no tree. The recursive `parent_id` walk in
`assert_unit_in_scope` therefore never treats Muttil North as a child of
Vythiri. Clicking village 8157 on the live map returned **403 `unit_scope`**
until the check also allowed

```sql
ST_Intersects(scope.geom, target.geom)
```

A Vythiri officer can open any ADM5 whose geometry intersects Vythiri
(39 villages). An ADM5 that only sat in Vythiri's **bbox** but not its
polygon stays 403; `/ops/map` now filters by officer geom so those
neighbours are not painted. Covered by
`tests/unit/test_rbac.py::test_officer_scope_covers_contained_village`.

Citizen PWA signs in through `POST /api/v1/auth/login`. It does not require
a pasted `VITE_CITIZEN_ACCESS_TOKEN`. Prefill email is `demo.citizen_email`
from public config. Passwords are bcrypt'd only when `SETU_DEMO_PASSWORD` is
set in `.env` (never in SQL).

Routers still to protect: none of the originally listed set — `assistance`,
`incidents`, `units`, `enrollment`, `response`, `ack`, `citizen` now depend
on `require_*` the same way `alerts.py` does. Receipts stay nonce-gated
(Part 26: "nonce-gated, not role-gated").

§12.2, as implemented:

- **auditor** on `/assistance` — 200, but `citizen_response_id`, `free_text`,
  `lat`, `lon` are omitted. Priority, status, unit, response type remain.
- **relay_node** on `/assistance` and `/assistance/{id}` — **403**. Count and
  area only, via `GET /assistance/summary` (`open_count` per unit, no
  response types, no household list).
- **citizen** write paths (`POST /ack`, `POST /response`,
  `GET /citizen/deliveries`, `GET /citizen/deliveries/{id}`) —
  `citizen` / `officer` / `state_admin` / `relay_node`. Auditor is 403.

`assigned_by` is taken from the authenticated principal, never the body
(same shape as `approver_id`).

---

### 6.11 The platform had never delivered anything

Found while asking "is the core loop actually end to end?" — and it was not.

**Every delivery in the system's history had failed.** `create_deliveries`
called `primary_channel_for_alert`, which returns the escalation policy's
first step — `fcm` for every severity — and applied it to every recipient.
No seeded recipient has a `push_token`, so `worker._resolve_address` raised
`recipient_no_push_token` every single time. 379 failed deliveries, zero
successful ones.

The consequence was worse than a broken send path: **D7f reachability was 0%
by construction.** Not because reach was genuinely zero, but because the send
aborted before it began, so `delivery_event` never got a `device_delivered`
row, and `reachability.reached_tier_floor = 2` could never be met. A metric
that cannot move is worse than no metric — and reachability is the number the
whole pitch leads with.

### The fix: channel is resolved PER RECIPIENT

`resolve_channels_for_recipients` replaces the single per-alert channel
choice. §8.5's model — *"three villages wired to real phones… the other 337
run the identical delivery engine against a simulated carrier"* — simply
cannot be expressed by one channel for the whole alert.

A recipient addressable on the policy channel gets the real adapter. One who
is not gets the simulated carrier, `simulated = true`, SIM badge. Governed by
`delivery.simulate_when_unaddressable`; set it false and unaddressable
recipients fail loudly instead, which becomes the correct setting once real
addresses exist.

**Why falling back is not dishonest:** it hides nothing. `delivery.simulated`
is set, the badge renders from it, and `channel_capability_tier` already names
sim's evidence source as `simulated_carrier_profile`. The alternative —
letting every delivery fail — is not more honest; it just produces a platform
that does nothing.

### The simulated carrier now completes the ladder

It recorded `provider_accepted` and stopped, so even successful simulated
sends could not lift reachability past tier 1. A real carrier confirms
delivery out-of-band (Twilio status callback, our own service worker calling
home); the simulator has no callback to wait for, so it models that
confirmation directly — at `simulated.device_delivered_rate` (0.92),
deliberately **below 1.0**, because provider-accepted is not device-delivered
and a ladder where every accepted message always arrives would teach the
officer the wrong thing.

### Verified end to end

One severe alert, two distinct officer approvals, dispatch, worker:

| | |
|---|---|
| Deliveries | **241 delivered**, 11 `simulated_carrier_failure` |
| Ladder | 241 `provider_accepted` → **224 `device_delivered`** |
| D7f reachability | **92.5% of registered recipients · 0.8% of estimated population** |

That last row is the two-denominator design (§4.1) doing exactly its job: the
platform reaches nearly everyone *enrolled* and almost nobody in the
*district*, because enrollment is the real bottleneck. The spec insists on
showing both precisely so that gap cannot be hidden behind a flattering
single number.

`tests/unit/test_channel_resolution.py` locks in both directions — an
unreachable recipient must be flagged, and a reachable one must **never** be
downgraded to the simulator (a bug that simulated everything would also make
the metrics move, so that direction needs its own test).

---

### 6.12 Five bugs a green test suite did not catch

All 37 tests passing at the time passed while live ingestion was completely broken. Every bug
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

### 6.13 What a line-by-line roadmap audit found (21 Aug 2026)

The roadmap was walked against the **running system** — database, code and
tests — rather than against this file's own previous claims. That distinction
mattered: 219 tests were green at the time, and every finding below had
survived all of them. Recorded because the *pattern* generalises.

**1. B3 was never implemented at all.** `escalation_policy` has carried
`wait_before_next_s`, `backoff_multiplier`, `jitter_ms` and `max_attempts`
since migration `0002`, fully seeded per severity. Grepping the whole tree for
those four names returned **only the migration and the seed file** — no code
read them. The evidence in the data was unambiguous:

| | Before | After |
|---|---|---|
| `delivery.attempt` values | `1` only, across all 1,987 rows | 30 rows reached attempt 2 |
| `escalated` state rows | **0** | 12 |
| Failures abandoned after one try | 462 | retried per policy |

A transient provider hiccup was a *permanent* delivery failure, on the primary
channel, in a disaster-alerting platform. B3 is `[C]` core Module B, not stretch.

It also silently broke **B9's semantics**. `on_channels_exhausted()` fired
inside the *first* `except ChannelUnavailable`, so the demo line "this unit
exhausted push, SMS **and** IVR" was true of one attempt on one channel. A
human is the most expensive channel in the table — `cost_weight` ranks it 12 —
and was being spent on the first hiccup. It now hangs off `chain_exhausted`,
reachable only once every step has been tried to its `max_attempts`.

The state machine had anticipated all of it: `LEGAL` already permits
`failed -> pending`, `failed -> escalated` and `escalated -> pending`, and
`keys.py` already reserved `zset_retry()`. Only the driver was missing.

Five design points in `retry.py` worth knowing before changing it:

- **`compute_delay_s()` is pure** and takes the policy row as arguments, so
  growth and jitter are testable without a fixture — and provable in a
  committed artifact (reproduced in **§12.1**).
- **Jitter is symmetric**, plus/minus half the configured window. Positive-only
  jitter would silently stretch every schedule past what the table says, which
  makes a tuned backoff untunable.
- **Due times live in a Redis ZSET**, not an `asyncio.sleep`. A redeploy is
  precisely when pending retries matter, and sleeping in-process drops every
  one of them. Draining claims with `ZPOPMIN` so two workers cannot both send
  the same person the same alert.
- **A channel can occupy more than one `step_order`.** `extreme` lists `sms` at
  step 0 (the Palghar fix — high reach-risk skips push) *and* at step 2, and
  `delivery` does not record which step it came from. `_policy_for()` resolves
  to the **last** match so escalation walks forward; resolving to the first
  would escalate a failed SMS *back* to the push step the policy deliberately
  skipped. That is a documented heuristic — the exact fix, if ever needed, is a
  `step_order` column on `delivery`, not a cleverer query.
- **`sim` gets no retry**, deliberately. It is a fallback, not a policy step;
  inventing a schedule for it would be a hardcoded timing by the back door.

**2. F3 approvals left no audit trace.** `services/governance/approvals.py`
had **no audit call whatsoever**. The four-eyes quorum was enforced correctly,
but `alert.approved` was never written — so the marquee governance feature was
invisible in the immutable ledger the 5:30 demo beat is built on, and Part 16
Day 6 names that event as a required timeline entry.

**3. `alert.validation_failed` was never written either.**
`POST /alerts/{id}/validate` persisted per-rule rows to
`alert_validation_result` but appended nothing to the ledger. That table is
per-rule *state*, not a ledger entry, so a blocked dispatch — step 3 of the
Day-9 integration run — produced no `audit_event` at all. Audited **after** the
rollback in `engine.py`, deliberately: the `QualityGateBlocked` raise unwinds
the transaction, so an append before it would vanish along with the dispatch.

**4. `PGCRYPTO_SYM_KEY` did not exist.** Absent from `.env`, `.env.example`,
`gen_secrets.py` *and* `check_env_example.py`. `_encrypt_phone()` returns
`None` rather than raising when the key is unset, so **20 CSV-imported
recipients had `phone_enc IS NULL`** and could never be reached by SMS, IVR or
email — with no error at import time. Four were recovered from
`data/enrollment/team.csv`; **sixteen are unrecoverable**, because their source
CSV is deleted and `phone_hash` is a one-way HMAC. Now documented in
`.env.example` as the data-shaping secret it is, alongside the pepper.

**5. FCM sent a `notification` block on the webpush path.** The browser's own
tray consumes those without ever waking our service worker — which is where the
`receipt_nonce` round-trip lives. `device_delivered` could never fire, so the
ladder would have frozen at tier 1, reproducing the exact failure §6.11 already
records once. Web push is now **data-only**, with `sw.ts` rendering the
notification itself.

**6. The dev service worker never started.** `createHandlerBoundToURL()`
*asserts* its URL is in the precache manifest and throws synchronously when it
is not. `vite-plugin-pwa` injects `__WB_MANIFEST` as `[]` in dev (Vite serves
the shell itself), so that throw aborted the whole worker at module evaluation.
Because it died there, every SW feature failed at once — which made one bug look
like several unrelated ones:

- **Gate 3's unplug beat** — the `NetworkFirst` route was never registered, so
  no alert was ever cached and the PWA had nothing to show offline.
- **The FCM `device_delivered` signal** — `enablePush()` awaits
  `navigator.serviceWorker.ready` before `getToken()`, and that promise never
  resolved. Push registration could not even be *attempted*, independently of
  notification permission.

The navigation fallback is now registered only when the shell is genuinely
precached. Production is unchanged — verified by reading the compiled guard out
of `dist/sw.js`, where the manifest carries `{"url":"index.html"}` and the
guard matches it. After the fix, `serviceWorker.ready` resolves in 2 ms and
`setu-deliveries-v1` holds the alert and its safe zone, reading back headline,
severity and Ed25519 signature with no network.

**Test gaps the same audit closed:** `geometry_non_empty` and
`target_count_plausible` had no fixture in either direction, though Day 4 names
both among the first three rules made real; `GET /units/{id}/vulnerability`,
`POST /response` and `POST /citizen/device` had no RBAC allow/deny pair;
F4 had no test proving a fourth **extreme** alert is still delivered in full;
and `STOP`/`opted_out_at` — a *consent* guarantee — had no test at all, even
though the exclusion existed in `recipients_in_area()`.

`verify_seeds.py` now **fails** rather than prints INFO on two Day-4 exit-gate
assertions it was only reporting: empty `app_config` notes (the three
`severity.rank` rows had none while their `extreme` sibling did — drift, not a
policy) and alerts with a NULL `incident_id`, of which three had accumulated
since the `0007` backfill because the column is nullable and nothing
re-checked it.

**The generalisable lesson, again:** every one of these was invisible to a
green suite because no test asserted on the *consequence* — the ledger's
contents after approving, the `attempt` column after a failure, the cache after
a page load. A test that exercises a code path is not the same as a test that
checks the path did what the product promises.

---

### 6.14 Going live: the deployed topology, and nine things that broke on the way

Deployed 21 Aug 2026. Four free-tier services, **₹0 total**, matching Part 22's
split exactly.

| Component | Host | URL |
|---|---|---|
| Citizen PWA | Vercel | `https://setucitizen.vercel.app` |
| Officer console | Vercel | `https://setuconsole.vercel.app` |
| API | Render (free web) | `https://setu-api-6ujx.onrender.com` |
| Postgres + PostGIS | Neon (Singapore) | `ep-damp-dust-az2n3wn2` |
| Redis Streams | Upstash (Singapore) | `fresh-kingfish-106444` |
| Delivery worker | **local process** → cloud data plane | `python run.py worker-cloud` |
| ML service | Hugging Face Space | **not deployed** |

#### Why the worker runs on a laptop

Render's free tier has **no background workers**. The blueprint asked for
`type: worker` with `plan: free`; Render accepted it and then *suspended* the
service, which surfaces only as a "Suspended (1)" tab on the services list. The
API stays green the whole time, so nothing looks wrong.

That is survivable because the worker is not a server: nothing calls it, and it
needs no inbound port — only Postgres and Redis, both now cloud-hosted. So
`python run.py worker-cloud` runs it locally against the deployed data plane,
and it is a genuine consumer of the real stream. `.env.cloud` (gitignored) holds
the credentials.

Two deliberate choices in that task:

- **It refuses to fall back to `.env`** when `.env.cloud` is missing. Draining
  the *local* queue while believing you are draining production is the worst
  outcome of a typo: the deployed dispatch would sit in Upstash forever with
  nothing consuming it, and every symptom would point at the API.
- **`PUBLIC_BASE_URL` points at the Render API, not localhost.** The worker
  builds Twilio status-callback URLs from it and Twilio must be able to reach
  them; pointing it locally silently breaks the `device_delivered` rung.

**Known limitation:** the worker dies when the laptop sleeps. For a demo that is
acceptable (and the live logs are arguably an advantage). For real operation it
needs Render Starter (~$7/mo) or to be folded into the API process.

#### Nine things that broke, and what each one teaches

**1. `pywin32` has no Linux wheel.** `requirements.txt` was frozen on Windows,
so the first Render build died with `No matching distribution found for
pywin32==312` — pip fails outright rather than skipping. Fixed with a PEP 508
marker. Rather than fix-and-rebuild-blind, the whole file was then dry-run
resolved inside a real `python:3.12-slim` container: it is the only
Windows-only entry, `colorama` merely looks like one, and all 17
native-extension packages ship manylinux wheels for 3.12.

**2. Part 23's Neon DSN advice is now wrong, and repeating it causes the bug it
was meant to prevent.** The spec says strip `?sslmode=require` because asyncpg
rejects it. Verified against the live instance: asyncpg accepts the full URL and
negotiates TLS itself — raw, fully-stripped and `ssl='require'` all connect.
What breaks is stripping *one* parameter, because Neon now issues
`?sslmode=require&channel_binding=require`; removing only the first leaves
`&channel_binding=require` glued to the database name:

```
InvalidCatalogNameError: database "neondb&channel_binding=require" does not exist
```

which reads as a missing database rather than a malformed URL.

**3. Env-group split-brain, and why it is invisible.** The blueprint declared
`envVarGroups: setu-shared`, so Render created it — but Render can only fill
*literal* values from a blueprint, and every credential is `sync: false`. The
group was created with two entries; the operator filled a differently-named
group by hand; the worker went on reading the empty one.

The failure mode is the instructive part. `setu-api` carries its own `envVars`,
so it serves logins, PostGIS queries and config perfectly while the worker boots
with no database and dies. Dispatch returns `200`, enqueues to Redis, and nothing
ever sends — on stage that is *"dispatched successfully"* with dots that never
turn green. `render.yaml` no longer declares the group at all; it references a
hand-managed one, with a comment explaining why.

**4. Secret Files are per-service.** `fcm.json` added to `setu-api` is not
visible to `setu-worker`. Since the worker is the process that actually calls
FCM, the file has to live on the *env group* (which propagates) or be added to
both. Miss it and `_ensure_firebase()` fails `os.path.isfile()`, raises
`ChannelUnavailable`, and every push silently routes to the simulated carrier —
reporting success.

**5. Vercel rejects unknown keys in `vercel.json`.** A `comment` field inside a
rewrite returns
`Invalid request: rewrites[0] should NOT have additional property comment`.
JSON has no comment syntax, so the reasoning for the rewrite exclusions lives in
**§10** of this file instead — with a note saying why, so nobody helpfully puts it
back.

**6. The SPA rewrite is load-bearing.** `vercel.json` excludes `/sw.js`,
`/registerSW.js`, `/manifest.webmanifest`, `/icon-*` and `/assets/*` from the
catch-all. A naive rewrite returns `index.html` for `/sw.js`, the browser
registers an HTML document as a service worker, and it dies — killing offline
caching *and* the FCM receipt, which is exactly the failure §6.13 records from a
different cause. Verified on the live deployment, not just in config:
`/sw.js` serves as `application/javascript; charset=utf-8`.

**7. A trailing slash in `CORS_ALLOWED_ORIGINS` blocks everything.** Browsers
send `Origin: https://setucitizen.vercel.app` — **never** with a trailing slash.
Configured with one, the API returns `access-control-allow-credentials` but no
`access-control-allow-origin`, so every request from the PWA is blocked by the
browser with nothing in the server logs to explain it. One character, total
outage, no error anywhere.

**8. `push_geometry_to_neon.py` is not safe to interrupt.** A timed-out
bootstrap left **5,500 duplicate ADM3 rows** on Neon (8,302 → 13,802), because
`lgd_code` is NULL on every row so the push has no natural key to be idempotent
on. Recovered via `fetched_at` as a discriminator after confirming all nine
foreign keys had zero references to the new rows.

**9. Vercel Root Directory drifting to the repo root.** `setuconsole`
must build from `web/console`. When the setting is empty, a production
push installs Python from the monorepo root and fails `npm run build`
in ~10 s. `setuconsole.vercel.app` stays on the last Ready alias — the
sidebar, Live chip and “no live warning” empty state look unfinished
even though main has them. Fixed 22 Aug by a CLI `--prod` from
`web/console` and setting `rootDirectory` back. Citizen was fine
because its Root Directory never drifted.

#### The signing-key trap

`VITE_ALERT_SIGNING_PUBKEY_B64` must be the public key **derived from the
`ALERT_SIGNING_SEED_B64` actually in use** — not a freshly generated one.
`scripts/gen_secrets.py` mints a new random keypair on every run, so using its
output here produces a PWA whose public key does not match the server's seed,
and `verify()` discards every signed alert as tampered. The correct value is
whatever `GET /api/v1/public/signing-key` returns. Confirmed identical on the
deployed stack, and confirmed baked into the served bundle.

#### Deployed state, verified end to end

| Check | Result |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| Real login vs Neon | 236-char JWT — proves `0013_auth` + provisioned hashes |
| `/auth/me` | `role=officer`, `unit_scope_id=3081` (Vythiri) |
| `/ops/map` | 39 village features, clipped to officer geometry |
| `/public/signing-key` | real Ed25519 key, matches the PWA bundle |
| `/public/config` | 5 firebase keys + VAPID, 42 keys total |
| PWA `sw.js` | `application/javascript` — rewrite guard held |
| PWA manifest + icons | `application/manifest+json`, both PNGs |
| CORS | must allow both Vercel origins (`setucitizen`, `setuconsole`) and `localhost:5173` / `:5174` — no trailing slash |
| Worker → Upstash | probe entry read, processed, acked (`entries-read=1`, `lag=0`) |

**Note on Upstash:** `XINFO GROUPS` reports `consumers=0` even while actively
consuming, so the consumer count is not a usable liveness signal there.
`entries-read` and `lag` are.

#### Still zero on the deployed stack

`SELECT COUNT(*) FROM delivery_event WHERE source='fcm_send'` is **0**. Every
piece of the push path is wired and verified; what remains is a human granting
notification permission on a real handset. Until then the primary channel is
unproven, which is Part 16 Day 4's exit-gate criterion.

---

### 6.15 Closing the two unmeasured Part 19 boxes, and a citizen-facing bug the deploy surfaced

Two Part 19 boxes had sat as "neither blocked nor done, just unmeasured"
since the audit in §6.13. Both closed the same day, with real measurements
rather than assumptions — and the second one found a genuine defect.

#### The four-tile DEM check (#25)

Part 29 gives the exact command:

```bash
aws s3 ls --no-sign-request \
  "s3://copernicus-dem-30m/Copernicus_DSM_COG_30_${tile}_DEM/"
```

Run as written, it returns nothing for all four tiles — which reads as
"all four missing." **That command is wrong.** The bucket's objects are keyed
`COG_10`, not `COG_30` — already noted independently in §3.6's "Copernicus DEM
tile keys are named `COG_10`, not `COG_30`" and used correctly in
`scripts/fetch_data.sh`, but Part 29's own prose in the master spec was never
corrected to match. Run with the right key, all four tiles — covering both
Wayanad and Palghar, with margin — are real, present `.tif` objects on the
live bucket. Dated log: **§12.3**.

#### The Redis command budget (#12), and what it found

Part 1.4 prices every v3.0 feature at 0–2 Redis commands **per alert run**.
B3 (§6.13) doesn't fit that model: `drain_due_retries()` calls `ZPOPMIN` on
**every worker loop tick**, including the idle one, which fires every
`delivery.xread_block_ms` (seeded 5000 ms) regardless of whether any alert has
been dispatched. That is a cost that scales with *wall-clock time the worker
runs*, not with alert volume — an axis Part 1.4's model never had to consider
because nothing before B3 polled Redis on every idle tick.

The arithmetic: `86,400,000 ms / 5,000 ms = 17,280 ticks/day`, each costing at
least one `ZPOPMIN`. **17,280 exceeds Upstash's entire 16,600/day budget on
idle polling alone, before a single alert is dispatched.** Given
`worker-cloud` (§6.14) is meant to be left running for the whole
rehearsal/demo window, this was the realistic failure mode, not an edge case.

Fixed by raising `delivery.xread_block_ms` from 5000 to 15000 — a config row,
not a literal, so the fix is a threshold change (Rule 1's whole point), applied
via `python run.py seed-config` and `neon-seed-config` to both databases, with
the running worker restarted to pick it up (the value is read once at startup).
15 s of added worst-case retry latency is immaterial against the policy's own
`wait_before_next_s` values of 45–120 s.

**Honest result, not rounded up:** at a generous 4-hour continuous-run
assumption with 10 real dispatches, the revised total lands at **4.08×
headroom** — short of the stated **5×** target. Full arithmetic is **§12.2**.
states this plainly and names the actual mitigation: stop the worker between
rehearsals rather than leaving it running across a full day, since the cost is
dominated by idle time, not alert volume.

#### The citizen PWA was showing a dev/test screen to real users

`docs/TASK.md` already documented the manual delivery-ID entry as
*"Manual delivery ID entry (works without Firebase for dev/test)"* — but the
code showed it unconditionally whenever no delivery was loaded, which is
every first visit before a real push has ever arrived. A citizen (or a judge)
opening the PWA for the first time saw a form asking them to type a numeric ID
they have no way to know, with no other option.

The real flow was already fully built and untouched by this fix: an alert
arrives as a push, `notificationclick` (`sw.ts`) opens the app straight to that
delivery, no typing involved. The bug was only in what rendered on the *empty*
state — before any alert has ever arrived for that citizen.

Fixed by gating the manual-entry form behind `import.meta.env.DEV` — Vite's own
build flag, true under `npm run dev`, false in the production bundle Vercel
serves — so no new config was needed, and the fix cannot regress silently:
confirmed by `grep` that the dev-only markup is entirely absent from the built
`dist/assets/*.js`. In its place, the empty-state screen now surfaces
**"Enable alerts on this phone"** — the same `POST /api/v1/citizen/device` path
already built for the loaded-alert view (§6.14), just given somewhere to render
before any alert exists. That is exposing an existing capability, not adding
one.

That gate was **not enough**. `npm run dev` still showed the ID box, and with
`fcm_send` at 0 the push-tap path cannot be the only way a signed-in resident
sees a warning. §6.16 removes the box and loads the village inbox instead.

---

### 6.16 Citizen inbox by enrolled village; officer desk in four languages

Two demo-blocking gaps after §6.15.

#### A resident must not type a delivery ID

Gating the ID form behind `import.meta.env.DEV` still left anyone running
the Vite citizen app (`:5174`) staring at a number box. Delivery `1` is the
first row in `delivery`, not a PIN and not "alert 1." A real resident has
no way to know it.

`GET /api/v1/citizen/deliveries` lists **active** alerts whose recipient
`unit_id` matches the session's `unit_scope_id`, one row per alert, newest
`effective_at` first. After login the PWA calls that list and opens the
first row. If the list is empty, the screen is **"No warning for your
village right now"** — honest, not a search box. `?delivery_id=` from
`notificationclick` (`sw.ts`) still works when a real FCM tap exists.

**Where "your village" comes from is enrollment, not GPS.** There is no
`app_user` → `recipient` foreign key. Recipients are CSV / SMS keyword;
the citizen session carries `unit_scope_id` assigned at provision
(`demo.unit_scope.citizen@setu.example` → **Muttil North**, ADM5 id
8157). Officers are **Vythiri** (ADM3 id 3081). GPS is requested only for
help types in `response.location_prompt_types`; if the resident refuses,
the help request still goes. Safe-zone search falls back to the village
centroid.

Auditor listing the inbox is **403**. Covered by
`tests/unit/test_rbac.py::test_citizen_inbox_returns_list` and
`test_auditor_cannot_list_citizen_inbox`.

#### Official feeds land as drafts and must be findable

USGS / GDACS persist as `lifecycle_status = 'draft'` and **never
auto-dispatch**. The composer used to prefer `active` rows, so official
drafts sat under a pile of manual alerts and the officer desk looked empty
of "real" events.

`GET /api/v1/alerts` accepts `source_id` and `authoritative`. Live Ops and
Composer fetch `source_id=usgs|gdacs` + `lifecycle_status=draft` and pin
**From official sites — not sent yet**. Sending is still Four-Eyes (or
source-authoritative) plus the quality gate. `python run.py ingest` is a
separate process from `python run.py api` — starting the API alone does
not pull feeds. GDACS `/geteventlist/SEARCH` can time out; the scheduler
retries every five minutes.

#### Officer copy and the hosted console

`web/console/src/lib/i18n.tsx` holds **en / hi / ml / mr**. `LangSwitcher`
sits on login and the topbar; `localStorage` key `setu.console.lang`;
`document.documentElement.lang` updates with it. Nav is plain language
(Map, Write warning, Help needed, Send a runner, Register people) and is
role-gated: compose / help / enroll for officer and state_admin; Send a
runner also for `relay_node`. Provenance chips stay visually distinct; the
empty On-foot page must **not** show “Person confirmed” — that chip means
a runner already attested, not the channel type. `scripts/a11y-check.mjs`
needles the `t("…")` keys.

Hosted at `https://setuconsole.vercel.app` (`web/console/vercel.json`).
Render `CORS_ALLOWED_ORIGINS` must include that origin next to the citizen
PWA, **no trailing slash**.

---

### 6.17 Push and IndicTrans2 have to fire on the laptop, not the Space

The hosted API still cannot load torch (Part 22) and still cannot reach a
process on this machine. A Hugging Face Space is the long-term host; until
one exists, the **laptop worker** is the honest path for both features.

**IndicTrans2.** `services/ml/server.py` used to tokenize English and
`generate()` with no language tags. IndicTrans2's own card says that
output is wrong without `IndicTransToolkit` plus FLORES-200 codes
(`ml` → `mal_Mlym`, `mr` → `mar_Deva`). The server now preprocesses,
generates, and postprocesses; missing toolkit is a 503, not a cached
garbage string. Mapping lives in `services/ml/flores.py` so the Space
image can copy it without pulling `asyncpg`.

`python run.py ml-load` starts `:8001` with `SETU_LOAD_ML_MODELS=1`.
`python run.py worker-cloud` and `python run.py translate-cloud` point
`HF_SPACE_URL` at `http://127.0.0.1:8001` when the cloud env has no real
Space URL. The worker calls `ensure_translations` **before** it builds
the FCM payload, so Malayalam is in `alert_translation` (and on the
wire) even though Render's compose-time call no-ops. For Kerala
**severe**, run `translate-cloud` after Save draft and before Validate
— the quality gate still reads Neon, not the laptop.

**Push.** `POST /citizen/device` now writes `preferred_lang` from
`lang_for_unit` (Muttil North → `ml`). The inbox prefers a
`citizen_pwa` delivery and resolves text in the village language, not
whichever CSV recipient happened to sort first. After the resident has
granted notification permission once, login re-registers the FCM token
so the next Send can actually reach the phone. `fcm_send` rows are
still only written by Firebase, never inserted by hand. On 22 Aug those
rows exist on live Extreme alert 6 — see §6.18.

Demo order: Enable alerts on the phone (or localhost Chrome) **before**
Send; keep `ml-load` and `worker-cloud` open.

---

### 6.18 22 Aug SIH live Extreme — what Neon actually held, and what lied

Live warning **alert id 6**, headline `thuderstorm test hai darna mat`,
**Extreme**, Malayalam + English, Two-Eyes, `lifecycle_status = active`,
Muttil North (ADM5 **8157**). Expires ~3:00 PM IST 22 Aug 2026. Do
**not** Send it again.

The product correction that day: on Extreme, **SMS and IVR are compulsory
for every numbered phone**, whether or not they opened the citizen app.
App push is extra. **Severe uses the same three channels**, but
`hold_staggered_channels` parks SMS and IVR on `zset:retry` so they wait
the previous step's `wait_before_next_s` (seeded 180 s after push, then
120 s after SMS) instead of firing in the same second. `create_deliveries`
inserts SMS + IVR when `phone_enc` is present and not simulated, and FCM
when `push_token` is present, de-duplicated by channel. The worker used to
`LIMIT 1` pending row per recipient and stop — only the first channel sent.
It now sends **all** pending/queued deliveries for that person that are
not still held.

#### Recipients on unit 8157

| id | kind | phone (last known) | what Extreme actually sent |
|---|---|---|---|
| 1 | citizen | `+917988243529` | real SMS + IVR + FCM |
| 2 | citizen | `+919711117266` | real SMS + IVR (no push token) |
| 3 | citizen | `+918797975654` | real SMS + IVR + FCM |
| 4 | citizen | `+919319277596` | real SMS + IVR + FCM |
| 5 | citizen_pwa | none (`citizen@setu.example`) | FCM failed (dead token); SMS/IVR `recipient_no_phone`; **simulated siren** delivered |

Twilio trial verified numbers (cap 5) are those four SIMs plus the trial
from-number. Trial IVR: the callee must press **any key** for Twilio’s
trial lady, **then** SETU 1 (safe) / 2 (help).

Officers: `officer.a@setu.example` / `officer.b@setu.example` (Vythiri
ADM3 **3081**). Password is `SETU_DEMO_PASSWORD` in `.env` (never
commit the value). Citizen email `citizen@setu.example` is recipient
**5**, not the SIM on recipient 1.

#### What counts as a reply for a given number

`citizen_response` is the only table that is a human answer. Three rows
existed for `+917988243529` at one point: two **sim** SAFE rows on
cancelled alert **5**, and one **real IVR 1 = SAFE** on alert 6
(`delivery_id` 8, `idempotency_key` `dtmf-8-1`, 22 Aug 07:45:43 UTC).
SMS “delivered” and FCM “acknowledged” are receipts, not replies.

Later the same number used the citizen PWA (delivery **9**, FCM). First
tap: `POST /ack` succeeded (`ack-83ab7f0f-…`, 08:12:51 UTC) and the PWA
showed **Pending / Saved. Will send as soon as there is a signal** while
the phone had Wi‑Fi. That copy is a **lie** — `sendResponse` treats
`TypeError` or `!navigator.onLine` as queued, but the page does not
persist the payload. Workbox Background Sync may queue a failed
cross-origin `POST /api/v1/response`; Chrome often never replays it
until an offline→online edge, so Help needed stayed empty. Retry after
the ack **did** land: `citizen_response` id **4**, type **`trapped`**,
08:32:48 UTC, `assistance_case` id **1**, channel **fcm**, not simulated.

#### Help needed showed 0 with a real case in Neon

`GET /api/v1/assistance` scoped officers with a recursive `parent_id`
walk. **Every one of 8,302 `admin_unit` rows has `parent_id IS NULL`**
(§6.16 / geoBoundaries ADM3 vs ADM5). Officer A/B are Vythiri (ADM3
**3081**). Muttil North **8157** is not a tree child, so the case was
filtered out even though `assert_unit_in_scope` already allowed
`ST_Intersects(scope.geom, target.geom)` (the two polygons **do**
intersect).

Live patch: `UPDATE admin_unit SET parent_id = 3081 WHERE id = 8157`
so the **already-deployed** Render list query could see the row without
waiting for a rebuild. The honest code fix is the same geographic
predicate as RBAC, in `assistance_queue.list_cases` and
`GET /assistance/summary` (`_IN_OFFICER_SCOPE`), covered by
`test_officer_assistance_lists_contained_village`.

`priority_factors` was stored as a JSONB **string** (`json.dumps` plus
asyncpg’s jsonb codec dumps again). `_case_out` now `json.loads` twice
if needed; `create_case` passes a dict and lets the codec encode once.

Give-to-team then ran: case 1 status **`en_route`**, team
**`relief_team`**.

#### Send a runner stayed empty for a different reason

**Help needed** = this person asked for rescue. **Send a runner**
(`GET /api/v1/relay/tasks`) = this **village** never got the warning
(`human_relay` deliveries in `pending` / `queued` / `sent`).

`on_channels_exhausted` only fires on B3 `chain_exhausted`. Recipient
5’s FCM/SMS/IVR failed, then the **simulated siren counted as
delivered**, so the chain never spent a human. Zero `human_relay` rows
until a pending delivery (**22**) was opened on alert 6 / recipient 5
so the desk could demonstrate confirm. Confirm is
`POST /api/v1/relay/tasks/{id}/confirm` (“I told people in person”),
also available to `relay.node@setu.example`. Muttil already has three
active `relay_node` rows (panchayat, police, ASHA). Seed phones remain
PLACEHOLDER-encrypted unless overwritten — do not `XADD` a live
Twilio call to those placeholders.

#### Other live defects the same afternoon

- **FCM `UnregisteredError` on recipient 5** crashed the Windows worker:
  the exception handler logged the error, then `UnicodeEncodeError` on
  `cp1252` killed the process. Mapped to
  `ChannelUnavailable("device_unregistered")`; that delivery **fails**
  (no simulated push). Worker must run with `PYTHONIOENCODING=utf-8`.
  PWA needs **Enable alerts** again for a live token.
- Render **web** and laptop **worker** must both run the Extreme
  multi-channel code. Render’s worker service stays **suspended**.
- Do not commit `.env.cloud`, FCM JSON, or `scripts/_tmp_*.py`.
- Hosted OTP: `POST /api/v1/auth/citizen/otp/request|verify`. Demo phone
  in config is `9000000000`; the four Twilio numbers issue real SMS
  codes. OTP sessions bind FCM onto **that SIM’s** recipient; email
  `citizen@setu.example` is the village `citizen_pwa` row (id 5), not
  `7988243529`.
- Officer desk copy after this run is in §7.6. Hosted
  `setuconsole.vercel.app` looks like the old desk until those files
  are on `main` and Vercel Root Directory stays `web/console`.

---

## 7. Frontend

Two apps that deliberately invert on almost every axis. Part 0.4 is explicit
that this is the governing decision of the whole design: *"any pattern we
borrow gets tagged with which of the two it belongs to."* Only three
components appear in both — the alert card, the assurance indicator and the
language selector — and each is **designed twice, not shared**. Nothing in
`web/console/src/styles/` may be imported by `web/citizen`.

| | Ops console (P1·P2·P5) | Citizen PWA (P3) |
|---|---|---|
| Holder | trained officer, seated, at a desk | frightened person, standing, possibly in the dark |
| Info per screen | many panels — comparison **is** the job | **one question** |
| Density | high (4/8/12/16 rhythm) | low, large targets |
| Body text | 14–16px | **18px minimum** |
| Theme | **dark-first** | **light-first** — a dark screen at night in a flood reads as "phone is dead" |
| Input | keyboard + command palette | one thumb |
| Motion | purposeful only | near zero |
| Network | assumed present | **assumed absent** |

### 7.1 The operations console (`web/console/`)

Vite + React 19 + TypeScript. Dark-first, high-density — the Linear /
Datadog / PagerDuty lineage named in Part 0.4.2. Officer-facing strings
go through `t()` (`en` / `hi` / `ml` / `mr`); see §6.16.

**Design rules, and how each was verified** (checked in the live DOM against
the running API, not asserted):

| Rule | Source | Verified as |
|---|---|---|
| Exact token palette | 11.1 | `--bg-base: #0b0d10`; every hex carries its measured contrast ratio in `tokens.css`, because "AA on every pairing" is only checkable if the numbers are written down |
| **Angular corner-cut panels**, not rounded | 0.5 (XCOM 2) | `clip-path: polygon(...)`, `border-radius: 0px` |
| JetBrains Mono + `tabular-nums` on every number | 11.1 ("non-negotiable") | `font-variant-numeric: tabular-nums` |
| Glow on **exactly one** severity tier | 0.5 | only `.sev--extreme`; suppressed under `prefers-reduced-motion` |
| Icon **and** text label, never colour alone | 11.1 | every badge, chip and rung |
| Fixed column widths, no layout shift on tick | 11.3 | `grid-template-columns` fixed + tabular-nums |
| `prefers-reduced-motion` collapses all motion | 0.5 ("no exceptions") | `--dur-count: 0ms`, glow removed — confirmed live |
| Command palette `Ctrl+K`, teaches its shortcuts | 0.4.3 | shortcut rendered per row |
| **No emoji as iconography** | 0.4.8 | `lucide-react` throughout, including the peer-relay "⇄" |

**Optimistic UI is banned** (11.3). Nothing renders as approved, dispatched or
delivered until the server confirms it; every mutation re-reads from the API
rather than patching local state. *"Showing 'acknowledged' before the server
confirms would be a lie in exactly the place lies are most dangerous."*

**22 Aug desk pass (after officers mixed Help needed with On foot):**
sidebar order is Map → Write warning → Help needed → **Send a runner** →
This emergency → Overview. Keyboard chords are not painted on the nav
(Ctrl+K still works). Help needed types the team name **on the row**;
urgency is 0–100, not `0.87`. Send a runner empty-state says the list
fills when phones fail, not when someone asks for help. Live Ops dropped
the three-step tutorial and the empty USGS panel. “They replied” on the
reach KPI is now **Opened or answered**. Citizen-reply KPIs are total /
safe / need help; SMS vs call vs app stay as filters. See §7.6.

**The three governance components carry their specified beats:**

- **`QualityGate`** — GitHub-PR-checks pattern (0.4.6). Six rows, the failing
  check **named**, and the reason sits *adjacent to the disabled dispatch
  button* — never a dismissible toast. Part 0.5: *"failing a gate must feel
  like a seatbelt, not a nag."* A `warn` (oversized area) is styled distinctly
  from a `fail` because it does **not** block.
- **`ApprovalPanel`** — the **missing** slot is full-contrast with a solid
  warning border while the *satisfied* slot is the quiet one. Part 0.5 is
  explicit and counter-intuitive here: *"the empty checkbox rendered at full
  contrast, not greyed — the UI's job here is to make the missing signature
  the loudest thing on screen."* Greying the gap would make it recede.
- **`AssuranceLadder`** — unprovable rungs render struck through with the
  **verbatim `not_applicable_reason` from `channel_capability_tier`**, plus
  an `sr-only` "— not applicable" so a screen reader does not read a struck
  label as a normal one. Nothing about channel capability is hardcoded in the
  component; the moment it contains a list of what SMS can do, the database
  stops being the source of truth and Rule 8 becomes a comment rather than a
  constraint.

**Verified live** on a real siren delivery: three rungs with
`text-decoration: line-through`, each carrying its real seeded reason
("A siren or public-address broadcast produces no digital receipt of any
kind…").

### 7.2 Two bugs found by running the console, not reading it

**The ladder sample buried its own best evidence.** Deliveries were sampled
`slice(0, 12)` by id, so the siren ladder — the single most informative one,
with three struck-through rungs — sat behind 250 identical simulated ladders
and never rendered. Now samples **one per channel first**, then most recent,
and states what it is showing rather than truncating silently (Part 0.5's
no-silent-caps guardrail).

**`SeverityBadge` displayed "Minor" for unknown severity.** It fell back to
`MAP.minor` for anything outside the four canonical tiers — and `unknown` is a
**real value in this database** (24 alerts, mostly GDACS levels that do not map
onto our scale). So alerts whose severity was never established rendered as
the *lowest* severity we have, inviting an officer to deprioritise something we
simply do not know about. Now renders as **Unknown**, dashed and neutral, with
the source value in the `title`. Same principle as the struck-through rung: *a
missing signal and a negative signal are different facts and must never render
identically.*

### 7.3 What the console still does not have

The event-time screens Part 0.4.3 named are built: Live Operations, Alert
Detail, Assistance, Incident, Command Board, Methodology, plus Analytics,
Relay, Enrollment, and Compose. WebSocket `/api/v1/ws/ops` drives the live
feed. Remaining gaps are operational, not missing screens:

- **Gate 3 cable-pull** is unrehearsed. The `.pmtiles` file and HTML village
  labels are local. Place-name / road / water **glyphs** still fetch
  `protomaps.github.io/basemaps-assets` when online; unplug and those labels
  vanish, village names stay.
- Console **refresh token is memory-only**. A tab reload drops it; the
  officer signs in again. That is deliberate (shared DEOC machine), not a bug.
- Uvicorn `--reload` will sit on "Reloading…" while a `/ws/ops` socket is
  open. Restart the API process after `rbac.py` / router edits or the browser
  keeps talking to the old worker.
- **Ack KPI ≠ citizen replies.** Live Ops “Opened or answered” is
  `delivery.state` / `acknowledged`. SAFE/HELP live in `ReplyInbox` and
  Help needed (cases only).
- Gate 3 airplane-mode reopen and a Hugging Face Space are still on the
  blocked list in `docs/TASK.md`. Live FCM, SMS, and IVR (including DTMF 1)
  are proven on alert 6 (§6.18). B10 on stage is a signed `?peer=` URL, not
  GATT (§8.1). Help no longer paints a fake Pending queue when the POST
  fails online (§7.6).

### 7.4 Live map (D1f), Compose (A3), and what is *not* on the map

The map is a **reachability choropleth**, not a hazard layer. That split is
the product:

| Surface | What it shows | Source |
|---|---|---|
| Live Ops map | Unit polygons coloured by `recipient_reach_pct`; labelled names | `GET /api/v1/ops/map` |
| Live Ops **From official sites** | USGS/GDACS drafts, not yet sent | `GET /api/v1/alerts` with `source_id` + `lifecycle_status=draft` |
| Live Ops table / "Where is trouble" | Ingested and manual alerts | `GET /api/v1/alerts` |
| Compose **From official sites** | Same official drafts | same query as Live Ops inbox |
| Compose draw | Officer-drawn polygon for a **new** warning | POST `/api/v1/alerts` GeoJSON |
| Unit panel | Reachability, vulnerability, reach-risk | `GET /api/v1/units/{id}/…` |

Active-alert polygons are **not** filled on Live Ops. Painting ingest
geometry there looked like a pre-marked danger zone and hid the officer's
job: read a source, then draw. A radar ping still fires for *newly arrived*
alert centroids on Live Ops only (`draw` mode skips it).

**Runtime bugs found by opening the pane, not reading the component:**

1. **MapLibre worker 404.** Vite prebundled a missing
   `/node_modules/.vite/deps/maplibre-gl-worker.mjs`. Fix:
   `setWorkerUrl` from `maplibre-gl/dist/maplibre-gl-worker.mjs?url` and
   `optimizeDeps.exclude: ["maplibre-gl"]`.
2. **India zoom + random ADM3.** Unscoped `/ops/map` used the India bbox and
   `LIMIT 800` with no `ORDER BY`. A scoped officer now gets their
   `unit_scope_id` envelope (Vythiri), then the **finest level in that
   envelope** (ADM5, 39 villages that actually intersect the taluk geom).
   Nationwide choropleth stays `map.geometry_level` (3).
3. **Yellow soup.** Dozens of test "Headline" polygons filled the pane.
   Alert fill/line layers were removed from Live Ops entirely.
4. **0-pixel pane.** `.live-map-wrap { min-height: 520px }` does not size a
   MapLibre container — the canvas is `position: absolute`. Without
   `.live-map { height: 520px }` the wrap reports height 0 and the map
   disappears while the rest of Live Ops still renders.
5. **Click 403 on a labelled village.** See **Unit scope at provision time**
   (`parent_id` empty; geographic `ST_Intersects`).

**Labels.** MapLibre symbol layers need a `glyphs` URL; the style now points
at Protomaps Noto Sans for `places` / `water` / `roads` when the basemap
source attaches. Village names do **not** depend on that — they are HTML
markers (`.map-unit-label`), one per unit, skipped if the payload has more
than 80 features (India ADM3 would be unreadable).

**Basemap extract.** `scripts/fetch_basemap.py` currently cuts India
`68,6,98,38` at maxzoom **6** (~2.6 MB). Earth/water/roads attach *after*
`load` so a missing `.pmtiles` cannot block the GeoJSON choropleth. Spec
Risk 22 still wants Wayanad + Palghar at z12; this file is the smaller
honest substitute until that extract is regenerated.

**Compose briefing.** The officer does not invent a hazard from a blank map.
Compose loads `/alerts`, lists incoming rows (source, severity, headline,
AUTO-AUTH). Clicking a row copies **that row's** severity and headline into
the form; Open goes to the existing alert. Severity starts empty — there is
no default `severe`. `target_count_plausible` is still correct: dispatch
needs ≥1 consented recipient whose unit geom intersects the drawn polygon.
`GET /units/{id}/vulnerability` no longer 404s if `v_communication_vulnerability`
has no row (the view `JOIN`s `unit_features`); it returns
`unknown_connectivity_features_pending` so a missing OpenCelliD feature
does not blank the unit page.

### 7.5 Operational figures in the console are class ①–④, never ⑤

Part 38.2: population, alerts, and hazards are not literals in TypeScript.

| Figure | Class | Where it comes from |
|---|---|---|
| Unit population / reach % | ① WorldPop in `admin_unit.population`, ② `v_reachability` | `GET /units/{id}/reachability` |
| Live Ops KPIs (targeted / delivered / ack / at-risk) | ② | `GET /ops/summary` — notes on the tiles are the SQL definition, not a made-up denominator |
| Alert list, ticks, Compose incoming | ① ingest + ③ officer drafts | `GET /alerts` (`source_id`, `is_authoritative`, `headline`) |
| Hazard / target area | ③ officer draw, or ingest `alert.area` on the **detail** of that row | never a static GeoJSON in `web/console` |
| Channel capability / struck rungs | ③ seeded `channel_capability_tier` | `GET /alerts/{id}/assurance` |
| Command Board tiles | ② D7f/D8f/D11f/B8 | `GET /incidents/{id}/board` — the component has no operational numeric literals (HTTP 403 is RFC) |
| Quality-gate pass/fail | ③ `app_config` floors, ② rule eval | `POST /alerts/{id}/validate`; UI labels `rule_id`, it does not invent results |

A village with NULL population renders **no population**, not a guessed
headcount. Compose copy does not name a demo village. Map ping does not
fall back to `minor` when severity is missing.

What *may* stay in the UI (Part 38 "what the thing is"): HTTP status codes,
assurance ordinals 0–5, CAP severity option values, icon sizes, map padding,
choropleth colour stops for a 0–100% scale.

### 7.6 Officer desk language after the 22 Aug Extreme (Help needed ≠ runner)

The desk had two lists that looked similar and one KPI that sounded like
a reply. Officers used **Give to team** on a trapped person, then opened
**On foot** expecting that person to appear. The runner list is empty
until a `human_relay` delivery exists. The names and empty-states now
say that out loud.

| Surface | Honest job |
|---|---|
| Help needed (`AssistanceQueue`) | People who asked for rescue (`assistance_case` from help types). Assign the team **on the row**. |
| Send a runner (`RelayTasks`) | Villages the phones never reached. Empty copy must not say “Person confirmed”. Confirm is “I told people in person”. |
| Reply inbox | `citizen_response` rows (SAFE / HELP). Three KPIs: total, safe, need help. |
| Live Ops ack tile | Opened the warning or answered it — not “they replied”. |

Files: `web/console/src/App.tsx` (nav order, no Ctrl-K chip / `G L` kbd
on the sidebar), `lib/i18n.tsx`, `pages/AssistanceQueue.tsx`,
`pages/RelayTasks.tsx`, `pages/LiveOps.tsx`, `components/ReplyInbox.tsx`,
`styles/layout.css` (sidebar 280px, larger table type). Register / How
we measure / Warning time sit under **Also**.

The citizen PWA used to paint “Saved. Will send as soon as there is a
signal” on a TypeError after ack even when the phone was online and
nothing was queued (§6.18). `sendResponse` now says the Help POST was
**not** sent and to tap again. Airplane mode shows “No signal. This is
the copy already on this phone.” That is Gate 3 without unplugging the
building (**§10.5**).

### 7.7 Citizen session persistence and the sideload APK

The officer console keeps tokens in `sessionStorage` on purpose — a shared
DEOC desk must not leave the previous officer signed in after the tab
closes (§7.3). The citizen app is the opposite: it is a personal phone,
and closing SETU must not force another OTP.

Until 22 Aug the citizen PWA used `sessionStorage` for
`setu_citizen_token` / `setu_citizen_refresh`. That is correct in a
browser *tab* and a defect in anything that destroys the document on
exit: Android WebView, and often an installed PWA after a swipe-away.
`web/citizen/src/api.ts` now reads and writes **`localStorage`**, and
migrates any leftover `sessionStorage` keys on first load. Sign out still
clears both.

**Sideload APK** (`mobile/citizen-apk/`, `python run.py citizen-apk`): a
debug-signed WebView shell of `https://setucitizen.vercel.app`. Not a
Play Store listing, not a native rewrite, not TWA. JDK 17 + the Android
SDK live in that folder’s Dockerfile so this laptop (Java 8, no SDK) can
still produce `mobile/citizen-apk/dist/SETU-citizen.apk`.

Two honesty limits, said before a judge finds them:

1. **FCM `getToken()` / Web Bluetooth are browser APIs.** They may fail
   inside Android System WebView. The presenting-device decision stays
   **Android Chrome → Add to Home Screen** (**§10.5**) for
   Enable alerts, the SW receipt, and Gate 3. The APK is the icon +
   login + ack/help shell.
2. **The APK does not bundle the Vite `dist`.** It loads the hosted PWA,
   so a Vercel deploy of the `localStorage` change is what makes the
   *website* persist; the APK also injects a document-start shim that
   mirrors the two session keys into `localStorage` so the *current*
   Vercel bundle (still compiled against `sessionStorage`) survives
   process death without waiting on that deploy.

Override the wrapped origin with `CITIZEN_PWA_URL` if you are not
pointing at Vercel. The APK is gitignored; rebuild rather than commit
the binary.

---

## 8. Open engineering questions

### 8.1 Community Relay Mode (B10) — Web Bluetooth role limitation

`shareNearby()` as designed calls `navigator.bluetooth.requestDevice()` and
connects as a GATT **client**. No shipping browser exposes the GATT
**peripheral/server** role to a web page — meaning Device A cannot advertise
a service for Device B to discover and write to. Phone-to-phone relay
through two PWA tabs, as specced, may not be achievable in a browser at all
(as opposed to being merely rate-limited by the user-gesture requirement,
which is a real but separate constraint).

**Signed-link fallback (22 Aug).** GATT peripheral is still impossible in
a browser. `web/citizen/src/relay.ts` shares a signed `?peer=` URL
(Web Share or clipboard). Phone B opens it in Chrome after sign-in; the
**PEER** chip renders only if Ed25519 verifies. Say “one hop, not a mesh,
not radio.” The APK WebView is not a native BLE wrapper.

### 8.2 ML service hosting

Isolated process exists: `python run.py ml` serves `services.ml.server` on
`:8001`. Weights load only with `SETU_LOAD_ML_MODELS=1`. Production still
needs a Hugging Face Space (or other host) — the API never imports torch
and only caches HTTP `/translate` / `/embed` responses.

### 8.3 Neon / cloud database

Neon is **set up and migration-verified** (§5.6). Full geometry bootstrap
ran via `python run.py neon-bootstrap` (`.env.neon`): **8,302** units
(ADM3 nationwide + ADM5 Kerala/Maharashtra), 281 safe zones, 5 Muttil
North recipients. Schema is at `0016`. Re-run `python run.py verify-data`
with `SETU_ENV_FILE=.env.neon` if a later load is suspected incomplete.

---

## 9. Repository layout

```
setu/
├── CLAUDE.md            binding project rules (not product docs)
├── README.md            HF Space frontmatter + how to run
├── services/
│   ├── api/             main.py, deps.py, schemas.py, config_repo.py, db.py
│   │   └── routers/     alerts, health, units, response, assistance, incidents,
│   │                    public, citizen, enrollment, webhooks, ack, receipts, ops, auth
│   ├── delivery/        engine, state_machine, assurance, worker, keys
│   │   └── channels/    base + simulated + fcm/sms/ivr/email/human_relay (env-gated)
│   ├── ingestion/       usgs/gdacs adapters, poller, scheduler, normalize, persist, incident_linker
│   ├── governance/      quality_gate (6/6), approvals, versioning, composer
│   ├── response/        citizen_response, assistance_queue, priority
│   ├── enrollment/      phone_hash, csv_import, sms_keyword
│   ├── targeting/       geo.py, escalation.py
│   ├── audit/           ledger.py, timeline.py
│   ├── crypto/          alert_signing.py (Ed25519 — server side)
│   └── ml/              isolated server on :8001; Space hosting still 🔴
├── web/
│   ├── console/         Ops console — Vite + React, dark-first (§7). Dev :5173
│   │   └── src/         lib/{api.ts, i18n.tsx, useOpsSocket.ts} · components/{LiveMap,
│   │                    AssuranceLadder, QualityGate, ApprovalPanel, CommandPalette,
│   │                    LangSwitcher, Kpi, SeverityBadge, ProvenanceChip, ReachabilityCard,
│   │                    RiskDial, ReplyInbox} · pages/{Login, LiveOps, Composer, AlertDetail,
│   │                    AssistanceQueue, Incident, CommandBoard, Methodology, Analytics,
│   │                    RelayTasks, Enrollment} · styles/{tokens, base, layout}.css
│   │   └── public/tiles/setu-basemap.pmtiles
│   └── citizen/         PWA — Vite + React + Workbox (src/sw.ts). Dev :5174
├── mobile/citizen-apk/  sideload WebView APK of the hosted PWA (§7.7)
├── data/seeds/          01–06 applied locally (06 = app_user roles)
├── migrations/          0001–0016 applied locally + Neon (schema; 0015 citizen OTP)
├── tests/               unit/ + property/ + fixtures/ — see docs/TASK.md last verification
├── scripts/             bootstrap, CI guards, geometry pipeline, upsert_app_config, db_config_sync
├── infra/               docker-compose.yml (Postgres :5433, Redis, MailHog)
├── .github/workflows/   ci.yml
├── run.py               task runner (Makefile replacement)
└── docs/                SETU_MASTER (spec), IMPLEMENTATION.md (this file), TASK.md
```

---

## 10. Deploy runbook

Absorbed here so the only product docs under `docs/` are this file, `TASK.md`,
and `SETU_MASTER_v3.0_MERGED.md`. Topology and the nine deploy failures remain
in §6.14; this section is the step-by-step runbook.

Four free-tier services, one repo. Total cost **₹0**.

```
Vercel  ──  citizen PWA  (HTTPS, static)     ─┐
Vercel  ──  officer console (HTTPS, static)  ─┤
Render  ──  API                              ├─ Neon (Postgres+PostGIS)
HF Space ── services/ml (torch, IndicTrans2) ─┘   Upstash (Redis)
```

**Why split this way:** Part 22. Render's free tier is ~512 MB and torch's
import footprint alone is 300–500 MB before either model loads. An all-in-one
image OOM-kills on the first real inference, and because the health check only
sees a process restart, that masquerades as "flaky cold starts" for days. The
API must never import torch — `scripts/check_no_torch.py` enforces it in CI.

**What the deploy unblocks.** Four roadmap items collapse at once, because all
four need one thing: an HTTPS origin a phone can reach.

| Item | Why it needs HTTPS |
|---|---|
| Real FCM `provider_accepted` | `getToken()` refuses a non-secure origin. `http://192.168.x.x` is not secure; `localhost` is, but a handset cannot reach your localhost |
| The SW receipt (ladder rung 2) | Needs a real push to arrive at a real service worker |
| Gate 3 unplug beat | Needs the PWA installed on the presenting phone |
| Twilio webhooks | Already work via tunnel, but the tunnel URL is ephemeral |

---

## 0. Before you start

You need four accounts, all free, none requiring a card:

| Service | What for | Gotcha |
|---|---|---|
| [Neon](https://neon.tech) | Postgres + PostGIS | Already done — `.env.neon` exists |
| [Upstash](https://upstash.com) | Redis | Free tier is command-metered. §1.4 has the budget arithmetic |
| [Render](https://render.com) | API + worker | Free web services **spin down after 15 min idle**; cold start ~50 s |
| [Hugging Face](https://huggingface.co) | ML Space | IndicTrans2 is **gated** — you must accept its terms while signed in |
| [Vercel](https://vercel.com) | Citizen PWA | None |

---

## 1. Hugging Face Space — `services/ml`

The Space builds from the **root `Dockerfile`**, which packages `services/ml`
only. The Space's repo is this repo; that avoids a vendored second copy of the
translate/embed endpoints, which is exactly how a Space and an API drift into
disagreeing about which model is loaded.

**1.1 Accept the model terms.** Sign in to HF, open
`huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M` and accept. Without
this the Space builds fine and then fails at first inference with a 401 from
the hub — a failure that looks like a bug rather than a licence gate.

**1.2 Create the Space.** New → Space. SDK **Docker**, hardware
**CPU basic (free)**. Name it something stable; the URL becomes `HF_SPACE_URL`.

**1.3 Set the Space secrets** (Settings → Variables and secrets):

| Key | Value | Kind |
|---|---|---|
| `SETU_LOAD_ML_MODELS` | `1` | Variable |
| `SETU_TRANSLATE_HF_ID` | `ai4bharat/indictrans2-en-indic-dist-200M` | Variable |
| `SETU_EMBED_HF_ID` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Variable |
| `INTERNAL_ML_KEY` | the value from your `.env` | **Secret** |

`SETU_LOAD_ML_MODELS=1` is the switch that makes the Space actually load
weights. It must stay `0` everywhere else — that is the isolation.

**1.4 Push.**

```bash
git remote add hf https://huggingface.co/spaces/<you>/<space-name>
git push hf main
```

**1.5 Verify.** The first build is slow (torch is a large download).

```bash
curl -s https://<you>-<space>.hf.space/health
```

Expect `"torch": true, "translate": true, "embed": true, "load_enabled": true`.
If `translate` is `false` while `load_enabled` is `true`, you did not accept the
gated terms in 1.1.

> **Known risk:** `IndicTransToolkit` sometimes needs `torch` present before it
> will build. If the Space build fails on that package, install it in a second
> `RUN` after torch rather than in the same `pip install`.

---

## 2. Render — API + worker

**2.1** New → Blueprint, point it at this repo. Render reads `render.yaml` and
creates `setu-api` (web) and `setu-worker`.

**2.2** Fill the prompted secrets. Every one is `sync: false`, so nothing
sensitive is in the repo. Take the values from your local `.env`:

- `DATABASE_URL_POOLED` — the Neon **`-pooler`** hostname, **copied exactly as
  Neon gives it, query string and all.**
- `DATABASE_URL_DIRECT` — the plain Neon URL, migrations only. Same rule.

  > **Do not partially strip the query string.** The spec (Part 23) says to
  > remove `?sslmode=require` because asyncpg rejects it. Verified against this
  > Neon instance on 21 Aug: that advice is now **wrong and actively
  > dangerous**. asyncpg accepts the full URL and negotiates TLS itself — all
  > three of raw, fully-stripped, and `ssl='require'` connect fine.
  >
  > What does break is removing *one* param. Neon now issues
  > `?sslmode=require&channel_binding=require`, so deleting just
  > `?sslmode=require` leaves `&channel_binding=require` glued to the database
  > name with no `?`, and you get:
  >
  > ```
  > asyncpg.exceptions.InvalidCatalogNameError:
  >   database "neondb&channel_binding=require" does not exist
  > ```
  >
  > which reads like a missing database rather than a malformed URL. Copy the
  > whole thing, or strip the whole query string. Never half of it.
- `REDIS_URL` — Upstash, **not** your local docker Redis.
- `PHONE_HASH_PEPPER`, `PGCRYPTO_SYM_KEY`, `ALERT_SIGNING_SEED_B64` —
  data-shaping secrets. Read Part 25's rotation notes first: rotating either of
  the first two is a **migration**, and the third is a **release**, because the
  public key is baked into the PWA bundle.
- `PUBLIC_BASE_URL` — this service's own `https://…onrender.com`. Twilio status
  callbacks are built from it, so a stale value silently breaks the ladder's
  `device_delivered` rung.
- `CORS_ALLOWED_ORIGINS` — your Vercel origins, comma-separated. Without this
  the browser blocks every call from the deployed PWA.
- `FCM_SERVICE_ACCOUNT_JSON` — Render has no file to point at. Either use a
  Secret File and set the path, or paste the JSON into an env var and adjust
  `settings.fcm_service_account_json` to accept inline JSON.

**2.3 Migrate.** Migrations use the **direct** URL — transaction-mode pooling
breaks session-level DDL:

```bash
DATABASE_URL_DIRECT="<neon direct url>" python -m alembic upgrade head
```

**2.4 Keepalive.** `.github/workflows/keepalive.yml` already pings both the API
and the Space every 10 minutes. Add repo secrets `API_URL` and `HF_SPACE_URL`
to arm it. Without this, Render sleeps and the first demo request eats a ~50 s
cold start.

---

## 3. Vercel — citizen PWA

**3.1** New Project → import the repo → set **Root Directory** to
`web/citizen`. `vercel.json` supplies the rest.

**3.2** Set build-time env vars (they are compiled into the bundle):

| Key | Value |
|---|---|
| `VITE_API_BASE` | `https://<your-render-api>.onrender.com` |
| `VITE_ALERT_SIGNING_PUBKEY_B64` | the public key printed by `scripts/gen_secrets.py` |

`VITE_API_BASE` must be set, and must have no trailing slash. Locally the PWA
uses a same-origin Vite proxy; deployed, it is genuinely cross-origin.

**3.3** Deploy, then add the resulting origin to Render's
`CORS_ALLOWED_ORIGINS` and redeploy the API. This ordering is unavoidable —
you cannot know the origin until Vercel assigns it.

**3.4 Sideload APK (optional, not Play Store).**
`python run.py citizen-apk` builds `mobile/citizen-apk/dist/SETU-citizen.apk`
in Docker — a WebView of `https://setucitizen.vercel.app`. Session keys
persist across app close (§7.7). Enable alerts / Gate 3 still need Chrome
→ Add to Home Screen (`IMPLEMENTATION.md` §10.5). The APK binary is gitignored;
rebuild rather than commit it. `CITIZEN_PWA_URL` overrides the wrapped
origin.

> **The SPA rewrite matters — do not "simplify" it.** `vercel.json` deliberately
> excludes `/sw.js`, `/registerSW.js`, `/manifest.webmanifest`, `/icon-*` and
> `/assets/*` from the catch-all. A naive rewrite returns `index.html` for
> `/sw.js`, which then registers as an HTML document and dies — the same class
> of failure that silently killed the dev service worker for the whole build.
> The negative lookahead was tested against every file the build actually emits.
>
> This explanation lives here rather than in `vercel.json` because Vercel
> validates that file against a strict schema and rejects unknown keys —
> including a `comment` field inside a rewrite:
>
> ```
> Invalid request: `rewrites[0]` should NOT have additional property `comment`.
> ```
>
> JSON has no comment syntax, so the reasoning has to sit outside the file.

## 3b. Vercel — officer console

Same account, **second** Vercel project. Root Directory **must stay**
`web/console`. Live: `https://setuconsole.vercel.app`.

If that setting is empty, a git push clones the repo root, `pip install`s
`requirements.txt`, then runs `npm run build` and dies with
`ENOENT … /package.json`. The custom domain keeps serving the last *Ready*
bundle, so the desk looks “stale” with no obvious failed deploy on the
apex URL. Confirm Root Directory after any dashboard click; the 22 Aug
push hit exactly this.

**3b.1** Build-time env (baked into the bundle, same rule as the PWA):

| Key | Value |
|---|---|
| `VITE_API_BASE` | `https://<your-render-api>.onrender.com` (no trailing slash) |

Local `npm run dev` leaves this empty so Vite's `/api` proxy still hits
`:8000`. The ops WebSocket (`/api/v1/ws/ops`) uses the same host as
`VITE_API_BASE` when it is set.

**3b.2** `vercel.json` rewrites every path to `index.html` except `/assets/`
and `/tiles/` (the India z6 pmtiles extract). No service worker on this app.

**3b.3** Add `https://setuconsole.vercel.app` to Render `CORS_ALLOWED_ORIGINS`
next to the citizen origin. No trailing slash — same trap as §3.3 /
§6.14 #7. Until that env is saved, the hosted console loads
but login is blocked by the browser with nothing in the API logs.

---

## 4. Prove it, don't assume it

Run these in order. Each one is a roadmap exit-gate criterion.

```bash
# API is up and talking to Neon
curl -s https://<api>/health

# The Firebase block reaches the browser (else "Enable alerts" never appears)
curl -s https://<api>/api/v1/public/config | grep firebase

# The Space is awake and loaded — or, until a Space exists, the laptop:
#   python run.py ml-load
curl -s http://127.0.0.1:8001/health
```

Expect `"torch": true, "toolkit": true, "translate": true, "load_enabled": true`.
`toolkit` false means IndicTransToolkit did not install — do not send; the
server will 503 rather than cache broken output.

`python run.py worker-cloud` and `python run.py translate-cloud` point at
`:8001` when `.env.cloud` has no real `HF_SPACE_URL`. After Save draft, run
`translate-cloud` before Validate if the warning is Kerala severe (Malayalam
required). Moderate can wait — the worker translates before the FCM send.

Then on the **presenting Android phone**, in Chrome:

1. Open the Vercel URL, sign in, tap **Enable alerts on this phone**, grant the
   prompt. This should be the first ever real FCM token.
2. Confirm it landed:
   ```sql
   SELECT id, unit_id, push_token IS NOT NULL FROM recipient
   WHERE kind = 'citizen_pwa';
   ```
3. Dispatch an alert, then check the ladder actually advanced past rung 1.
   Alert 6 already has `fcm_send` for recipients 1, 3, 4; recipient 5 needs
   Enable alerts again before the next Send:
   ```sql
   SELECT event_type, source FROM delivery_event
   WHERE source IN ('fcm_send', 'service_worker') ORDER BY id DESC LIMIT 5;
   ```
   `fcm_send` proves the send; `service_worker` proves the phone called home.
4. **Install the PWA in Chrome** (⋮ → Add to home screen), then put the phone in
   airplane mode and reopen it. The alert must still render — Gate 3.
   The sideload APK is not this beat.

---

## 5. Point Twilio at the real URL

Console → Phone Numbers → your number:

| Field | Value |
|---|---|
| A message comes in | `https://<api>/api/v1/webhooks/sms-inbound` |
| Status callback URL | `https://<api>/api/v1/webhooks/sms-status` |

Then retire the ngrok tunnel and set `PUBLIC_BASE_URL` to the Render URL. The
tunnel stays useful for local development, but a free ngrok URL changes on every
restart, so it must not be what the demo depends on.

---

## What is still not deployable

- **B10 GATT peripheral.** No shipping browser exposes that role, so
  radio hop between two PWA tabs is not shippable. The demo path is a
  signed `?peer=` URL (Web Share / clipboard) verified with Ed25519
  (§8.1, §10.5). Cut order already pre-authorises dropping native BLE.
- **Nationwide real SMS.** Needs TRAI DLT registration — a registered legal
  entity and ~10 business days. Every simulated delivery is flagged
  `simulated = true` and badged `SIM`; the engine, state machine and escalation
  are identical on both paths.

---

## 10.5 Presenting device and how to show unrehearsed beats

Presenting device for **push, Gate 3, and peer-relay**: **Android Chrome**
(not iOS Safari, not the sideload APK).

Covers both weak spots from spec §11.4:

- Offline PWA / Gate 3 unplug beat
- Web Bluetooth peer relay (Chromium-only)

iOS Safari is not used for the live demo. If Bluetooth fails twice in rehearsal, B10 is shown from a **signed link** on a second Chrome tab/phone, not from a recording.

**Sideload APK** (`python run.py citizen-apk` →
`mobile/citizen-apk/dist/SETU-citizen.apk`) is an optional home-screen
icon: a WebView of `https://setucitizen.vercel.app`, not Play Store.
Login/ack/help persist across app close (`localStorage` + WebView shim,
§7.7). **Do not** use it for Enable alerts or the
unplug beat — Android WebView does not expose the Push API the way
Chrome does. Install the PWA from Chrome for that half of the demo.

## How to show the beats that cannot run as specced

**Gate 3 (cable-pull).** Code caches the open alert. Do not unplug the
building. After the alert is on screen in **Android Chrome → Add to Home
Screen**, turn on **Airplane mode**, kill Chrome, reopen SETU from the
home-screen icon. The banner “No signal. This is the copy already on this
phone.” is the beat. Safe/Help while offline will say they were **not**
sent — tap again after signal; do not claim a pending queue.

**B10 (two-phone Bluetooth).** A web page cannot advertise GATT. On
phone A tap **Share with someone nearby**. Chrome will share or copy a
**signed URL**. Open that URL in Chrome on phone B. The **PEER** chip
appears only after Ed25519 verifies. Say out loud: one hop, not a mesh,
not radio.

**C3 (live IndicTrans2).** No Hugging Face Space. Before Validate on a
new Muttil Extreme: `python run.py ml-load` then `python run.py
translate-cloud`. Show Malayalam on the PWA from `alert_translation`.
If the fallback notice appears, that is the honest miss.

**B9 IVR relay confirm.** Citizen IVR 1/2 is real. The *runner* confirm
on stage is the console **I told them in person** button (`method=http`).
Say the DTMF runner path exists and has not been called live.

**21-step recorded take / two-device Two-Eyes 10×.** Show 409 `{have:1,
need:2}` on the presenting laptop, then Officer B on the second login.
Do not promise the choreographed 10× run.

**HF Space / Slack webhook / sixth Twilio number.** Not demoable. Name
them as accounts we do not have.

**Send a runner empty.** A new Extreme after this worker build opens a
runner when the only “delivered” channels were simulated (recipient 5’s
siren case). Do not expect a runner on already-sent alert 6.

---

## 11. Part 19 — Definition of Done, walked line by line

**Day 11 deliverable.** Part 16's Day-11 DoD is *"Full merged Definition of
Done (Part 19) walked line by line — every box ticked or explicitly waived
with a reason."* This is that walk.

**Walked:** 21 Aug 2026, against the running system — Postgres `:5433`,
Redis `:6379`, the live API, the built PWA bundle and real providers. Not
against this file's earlier claims. Where a box could not be verified by
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
| 3 | A real push **and** a real SMS arrive on real phones | ⚠️ | **SMS: done** — real `provider_accepted` (`twilio_sms_send`) then a real carrier callback writing `device_delivered` (`twilio_sms_webhook`), signature-verified, to a verified handset. **Push send: done 22 Aug** — live Extreme alert 6 wrote `fcm_send` `provider_accepted` for Muttil recipients 1, 3, 4. Recipient 5 is `device_unregistered` (honest fail — Enable alerts again before the next Send). **SW home-call (`source='service_worker'`)** is the remaining half of rung 2; do not claim device-delivered for FCM until that row exists on the presenting phone. |
| 4 | Every simulated delivery flagged in the DB **and** badged in the UI | ✅ | 308 rows with `simulated = true`; the `SIM` badge renders from that column (seen in the live PWA), and `channel_capability_tier` names sim's evidence source as `simulated_carrier_profile`. |
| 5 | Audit chain verifies, and `UPDATE audit_event` raises live | ✅ | `audit_immutable` trigger present on `audit_event` (`BEFORE UPDATE OR DELETE`). Confirmed incidentally during this work: three test alerts could **not** be deleted because the trigger refused. |
| 6 | Dedup precision/recall measured on a held-out set, published in the UI | ✅ | 200 labelled pairs in `data/ml/dedup_heldout.json`; P/R published to `model_registry` (4 rows) and rendered on the Methodology screen. |
| 7 | Reach-risk carries a visible **bootstrap** badge + disclosure text | ✅ | `reach_risk.disclosure.missing` seeded in `app_config`; `is_bootstrap` never cleared; `RiskDial` renders the badge. |
| 8 | `/api/v1/methodology` returns every threshold, metric, limitation | ✅ | Route registered and serving; drives the Methodology screen. |
| 9 | `check_no_hardcoding.py` passes in CI | ✅ | Green, three passes (Python AST · SQL views · TS), wired in `.github/workflows/ci.yml`. |
| 10 | **Branch coverage ≥95% on the delivery state machine, re-verified after every v3.0 writer** | ✅ | **95.87%**, re-run after B3's writers were added — which is exactly the re-verification this box asks for. `state_machine.py` and `states.py` are both at 100%. |
| 11 | All six teammates can run the demo alone | ❌ | Day 12–13 rehearsal. Needs the team. |
| 12 | Redis command budget ≥5× headroom | ⚠️ | *(deploy)* Re-derived from real data (33 dispatches): found B3's idle-tick `ZPOPMIN` cost **17,280 commands/day alone**, exceeding the whole daily budget before any alert fires. Fixed by raising `delivery.xread_block_ms` 5000→15000 (config, not a literal). At a generous 4-hour continuous run: **4.08× headroom** — short of 5× unless the worker is stopped between rehearsals, which the evidence doc states plainly rather than rounding up. `IMPLEMENTATION.md §12.2`. |
| 13 | USGS/GDACS ingestion, zero auth, confirmed live | ✅ | Both adapters run against the live zero-auth endpoints; 218 `alert.ingested` audit events. GDACS uses `/SEARCH` (the spec's `/MAP` 400s without `eventtype`). |
| 14 | Thunderstorm nowcast scores a real India district from live Open-Meteo | ⚠️ | `ThunderstormNowcastAdapter` exists and is unit-tested, but its `alert_source` row is seeded `enabled = false`, so it has never polled live. The seed comment ("enabled once the adapter exists") is stale now that it does. |
| 15 | Citizen PWA resolves a nearest safe zone from real OSM rows | ✅ | Verified in the live PWA: *"Community Hall, Muttil · community_centre · 820 m"*, from the 281 Overpass-sourced `safe_zone` rows, with the road-conditions disclosure. |
| 16 | Translation runs on the 200M model on the actual free-tier host | ❌ | No HF Space deployed. `HF_SPACE_URL` is a placeholder. The API caches over HTTP only and never imports torch; PWA/IVR/relay fall back with a visible notice. |
| 17 | `app_config` + extended `escalation_policy` seeded — every threshold a row | ✅ | 196 config rows, **0** with an empty note (three `severity.rank` rows were blank; fixed), 13 escalation-policy rows. `verify_seeds.py` now *fails* on drift instead of printing INFO. |
| 18 | `services/ml` runs as its own Space; `services/api` has zero torch imports | ⚠️ | The isolation is real and enforced — `check_no_torch.py` green, `python run.py ml` runs `services.ml.server` on `:8001`, weights load only under `SETU_LOAD_ML_MODELS=1`. *(deploy)* The Space image is now **built and run-tested**: `/health` reports honestly, `/translate` returns 503 `models_absent` instead of crashing, and a wrong `X-Internal-Key` returns 401. The *hosting* half is still not done (see #16). |
| 19 | Pooled URL for the app, direct URL for migrations | ✅ | `DATABASE_URL_POOLED` / `DATABASE_URL_DIRECT` split in `settings.py`; `alembic` uses the direct DSN. |
| 20 | **Retry backoff shows visible growth + jitter in a captured log from a forced-failure test** | ✅ | **This was unsatisfiable until today** — B3 was dead code (see §6.13). `IMPLEMENTATION.md §12.1` is generated from the live policy rows: growth 60 → 90 → 135 s, jitter spread ±2.5 s, mean on the policy curve. Pinned by 16 tests. |
| 21 | `.env.example` and the Part 25 table match; CI fails on drift | ✅ | `check_env_example.py` green. Grew by six keys today (five Firebase + `PGCRYPTO_SYM_KEY`). |
| 22 | RBAC matrix is a table in the repo and every row has a test | ✅ | Part 26 is the table; **140** RBAC tests. Three rows had no allow/deny pair (`/units/{id}/vulnerability`, `POST /response`, `POST /citizen/device`) and now do. |
| 23 | `freeze-guard.yml` live, and its block demonstrated once deliberately | ⚠️ | Live, guarding all Day-11 paths, epoch 21 Aug 21:00 IST. The block **cannot** be demonstrated until that timestamp passes — a few hours out at walk time. |
| 24 | Redis-budget and health-check webhook pings each fired once | ❌ | `SLACK_OR_DISCORD_ALERT_WEBHOOK` is empty. Needs a webhook URL. |
| 25 | Four-tile DEM check has a committed, dated pass/fail log | ✅ | *(deploy)* Run for real against the Copernicus S3 bucket with `--no-sign-request`. Part 29's own literal command uses the wrong prefix (`COG_30`); corrected to `COG_10` (confirmed by listing), all 4 tiles present for Wayanad + Palghar, no SRTM fallback needed. `IMPLEMENTATION.md §12.3`. |
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
| 54 | Device decision written into `IMPLEMENTATION.md` §10.5, not revisited after Day 8 | ✅ | Android Chrome, with the reasoning (covers both offline-PWA and Web-Bluetooth weak spots). Bluetooth GATT peripheral is impossible in a browser; the live fallback is a signed `?peer=` URL on a second Chrome tab/phone (§10.5), not a recording. |

## Part 38 — the two audits

| # | Box | Status | Evidence / reason |
|---|---|---|---|
| 55 | All five Part 38.1 hardcoding violations fixed; guard runs all three passes + TwiML test | ✅ | Green. Guard strengthened during §6.12 to see *default arguments* (it previously only inspected `Compare`/`BinOp`), and verified to actually fail on a probe file before being trusted. |
| 56 | `verify_seeds.py` asserts 74 `app_config` and 8 `channel_capability` rows before anything starts | 🚫 **Waived, deliberately** | The script asserts ≥110 config rows and 32 `channel_capability_tier` rows instead, and says why in its own docstring: the spec's "74 / 8" is stale, and `channel_capability` became a *view* over a 4-tiers × 8-channels table in migration `0009` because one `not_applicable_reason` column cannot hold a reason per tier. Asserting the spec's numbers would make this script the second place the count drifted, not the fix for the first. |
| 57 | **The basemap renders with the network unplugged** — verified during a Gate-3 run | ⚠️ | The file is committed and configured: 2.6 MB `setu-basemap.pmtiles`, `map.tile_source = pmtiles_local`. Not yet verified *during an actual unplugged run*, and place-name glyphs still hit a CDN when online (village names are HTML labels and work without them). |
| 58 | Twilio credit ≥2 voice calls and ≥5 SMS at T-30 min; B6/B9 rehearsed on the simulated adapter | ⚠️ | Credit is ample: **$9.32**, ≈112 SMS at the measured ₹7/message India rate. **B6 voice is no longer unexercised:** alert 6 delivery 8 is a real IVR + DTMF 1 = SAFE. B9 **relay** confirm via `ivr_dtmf` has still never run (HTTP confirm exists). Trial callee must press any key, then 1/2. |
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
code (HTTPS deploy landed 21 Aug; live FCM/SMS/IVR on 22 Aug — remaining
gaps are a handset, a second human, or an account):

1. **A handset beat that is coded but unrehearsed** — Gate 3 cable-pull,
   FCM `service_worker` receipt on the presenting phone, SW-cached ack
   with the cable out.
2. **No second human / no phone answered in the *relay* path** — B9
   `ivr_dtmf` confirm, dual-auth on two physical devices, the 21-step
   take, the six run-throughs. Citizen IVR DTMF 1 is proven.
3. **No second device** — B10 Bluetooth (and `§8.1` flags it as possibly
   impossible in a browser: **spike before budgeting engineering time**).
   The sideload APK is a WebView of the PWA, not native BLE.
4. **An account we do not have** — HF Space for IndicTrans2, a Discord/Slack
   webhook for monitoring.

**(deploy)** — #25 and #12 were the two exceptions: neither blocked nor done,
just unmeasured. Both closed same-day: the DEM check found all four tiles
present (once Part 29's own command was corrected), and the Redis re-derivation
found a real problem — B3's idle polling alone exceeded the daily budget — and
fixed it with a one-line config change, landing at 4.08× headroom rather than
the stated 5×.

---

## 12. Dated evidence logs

Canonical copies of the 21 Aug artifacts. Regenerating backoff: run
`python scripts/capture_backoff_log.py --date YYYY-MM-DD` and paste the
stdout into §12.1.

### 12.1 Retry backoff — captured 2026-08-21

Part 19: *"Retry backoff shows visible growth + jitter in a captured log from a forced-failure test."* Generated by `python scripts/capture_backoff_log.py --date 2026-08-21` against the live `escalation_policy` rows — these are this deployment's real seeded values, not an illustration.

Jitter is sampled 400x per step with a fixed seed (20260821) so the artifact is reproducible. `compute_delay_s()` applies geometric growth on `wait_before_next_s` and then symmetric jitter of +/- half `jitter_ms`, so the mean stays on the policy curve instead of drifting past it.

## extreme - step 0 - `sms`

`wait_before_next_s=60` `backoff_multiplier=1.5` `jitter_ms=5000` `max_attempts=2`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 60.000s | 57.510s | 60.087s | 62.491s | 4.982s |
| 2 | 90.000s | 87.509s | 89.935s | 92.496s | 4.987s |
| 3 *(beyond max_attempts - escalates)* | 135.000s | 132.501s | 134.867s | 137.457s | 4.957s |

## extreme - step 1 - `fcm`

`wait_before_next_s=90` `backoff_multiplier=1.5` `jitter_ms=5000` `max_attempts=2`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 90.000s | 87.510s | 90.087s | 92.491s | 4.982s |
| 2 | 135.000s | 132.509s | 134.935s | 137.496s | 4.987s |
| 3 *(beyond max_attempts - escalates)* | 202.500s | 200.001s | 202.367s | 204.957s | 4.957s |

## extreme - step 2 - `sms`

`wait_before_next_s=60` `backoff_multiplier=1.5` `jitter_ms=5000` `max_attempts=2`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 60.000s | 57.510s | 60.087s | 62.491s | 4.982s |
| 2 | 90.000s | 87.509s | 89.935s | 92.496s | 4.987s |
| 3 *(beyond max_attempts - escalates)* | 135.000s | 132.501s | 134.867s | 137.457s | 4.957s |

## extreme - step 3 - `ivr`

`wait_before_next_s=45` `backoff_multiplier=1.0` `jitter_ms=2000` `max_attempts=1`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 45.000s | 44.004s | 45.035s | 45.997s | 1.993s |
| 2 *(beyond max_attempts - escalates)* | 45.000s | 44.003s | 44.974s | 45.998s | 1.995s |
| 3 *(beyond max_attempts - escalates)* | 45.000s | 44.000s | 44.947s | 45.983s | 1.983s |

> Flat by policy (`backoff_multiplier = 1.0`). Growth is a per-step choice, not a global behaviour.

## extreme - step 4 - `siren`

`wait_before_next_s=0` `backoff_multiplier=1.0` `jitter_ms=0` `max_attempts=1`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 0.000s | 0.000s | 0.000s | 0.000s | 0.000s |
| 2 *(beyond max_attempts - escalates)* | 0.000s | 0.000s | 0.000s | 0.000s | 0.000s |
| 3 *(beyond max_attempts - escalates)* | 0.000s | 0.000s | 0.000s | 0.000s | 0.000s |

> Flat by policy (`backoff_multiplier = 1.0`). Growth is a per-step choice, not a global behaviour.

## extreme - step 5 - `human_relay`

`wait_before_next_s=120` `backoff_multiplier=1.0` `jitter_ms=0` `max_attempts=2`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 120.000s | 120.000s | 120.000s | 120.000s | 0.000s |
| 2 | 120.000s | 120.000s | 120.000s | 120.000s | 0.000s |
| 3 *(beyond max_attempts - escalates)* | 120.000s | 120.000s | 120.000s | 120.000s | 0.000s |

> Flat by policy (`backoff_multiplier = 1.0`). Growth is a per-step choice, not a global behaviour.

## severe - step 1 - `fcm`

`wait_before_next_s=180` `backoff_multiplier=1.5` `jitter_ms=8000` `max_attempts=2`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 180.000s | 176.015s | 180.140s | 183.986s | 7.971s |
| 2 | 270.000s | 266.014s | 269.895s | 273.993s | 7.979s |
| 3 *(beyond max_attempts - escalates)* | 405.000s | 401.001s | 404.787s | 408.932s | 7.931s |

## severe - step 2 - `sms`

`wait_before_next_s=120` `backoff_multiplier=1.5` `jitter_ms=8000` `max_attempts=2`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 120.000s | 116.015s | 120.140s | 123.986s | 7.971s |
| 2 | 180.000s | 176.014s | 179.895s | 183.993s | 7.979s |
| 3 *(beyond max_attempts - escalates)* | 270.000s | 266.001s | 269.787s | 273.932s | 7.931s |

## severe - step 3 - `email`

`wait_before_next_s=300` `backoff_multiplier=1.0` `jitter_ms=0` `max_attempts=1`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 300.000s | 300.000s | 300.000s | 300.000s | 0.000s |
| 2 *(beyond max_attempts - escalates)* | 300.000s | 300.000s | 300.000s | 300.000s | 0.000s |
| 3 *(beyond max_attempts - escalates)* | 300.000s | 300.000s | 300.000s | 300.000s | 0.000s |

> Flat by policy (`backoff_multiplier = 1.0`). Growth is a per-step choice, not a global behaviour.

## severe - step 4 - `human_relay`

`wait_before_next_s=300` `backoff_multiplier=1.0` `jitter_ms=0` `max_attempts=1`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 300.000s | 300.000s | 300.000s | 300.000s | 0.000s |
| 2 *(beyond max_attempts - escalates)* | 300.000s | 300.000s | 300.000s | 300.000s | 0.000s |
| 3 *(beyond max_attempts - escalates)* | 300.000s | 300.000s | 300.000s | 300.000s | 0.000s |

> Flat by policy (`backoff_multiplier = 1.0`). Growth is a per-step choice, not a global behaviour.

## moderate - step 1 - `fcm`

`wait_before_next_s=300` `backoff_multiplier=1.5` `jitter_ms=10000` `max_attempts=2`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 300.000s | 295.019s | 300.175s | 304.983s | 9.964s |
| 2 | 450.000s | 445.017s | 449.869s | 454.991s | 9.974s |
| 3 *(beyond max_attempts - escalates)* | 675.000s | 670.001s | 674.734s | 679.915s | 9.914s |

## moderate - step 2 - `email`

`wait_before_next_s=600` `backoff_multiplier=1.0` `jitter_ms=0` `max_attempts=1`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 600.000s | 600.000s | 600.000s | 600.000s | 0.000s |
| 2 *(beyond max_attempts - escalates)* | 600.000s | 600.000s | 600.000s | 600.000s | 0.000s |
| 3 *(beyond max_attempts - escalates)* | 600.000s | 600.000s | 600.000s | 600.000s | 0.000s |

> Flat by policy (`backoff_multiplier = 1.0`). Growth is a per-step choice, not a global behaviour.

## minor - step 1 - `fcm`

`wait_before_next_s=0` `backoff_multiplier=1.0` `jitter_ms=0` `max_attempts=1`

| attempt | no-jitter delay | observed min | mean | max | spread |
|---|---|---|---|---|---|
| 1 | 0.000s | 0.000s | 0.000s | 0.000s | 0.000s |
| 2 *(beyond max_attempts - escalates)* | 0.000s | 0.000s | 0.000s | 0.000s | 0.000s |
| 3 *(beyond max_attempts - escalates)* | 0.000s | 0.000s | 0.000s | 0.000s | 0.000s |

> Flat by policy (`backoff_multiplier = 1.0`). Growth is a per-step choice, not a global behaviour.

## What this shows

- **Growth**: every step with `backoff_multiplier > 1.0` produces a strictly increasing no-jitter delay per attempt. This is v2.1 loose end #4 closed (Part 24): a flat wait treated a channel down for one second the same as one down for ten minutes.
- **Jitter**: the min/max columns differ within every step that sets `jitter_ms > 0`, so a whole fan-out does not retry in lockstep against a provider that is already struggling.
- **Mean tracks the policy**: the observed mean sits on the no-jitter delay, because jitter is symmetric. Positive-only jitter would silently stretch every schedule beyond what the table says.
- Steps that are flat but still jittered (extreme/ivr): no growth by policy, but the herd is still spread.

Enforced by `tests/unit/test_retry_and_escalation.py` — growth, jitter bounds, jitter symmetry, and the non-negative clamp each have their own test, so this artifact cannot silently drift from the code.

### 12.2 Redis command budget — re-derived after B3 — 21 Aug 2026

Part 19: *"Redis command budget has ≥5× headroom for demo day."* Part 1.4
re-derives this at ~305–310 commands per full alert run and names the Part 28
80% threshold (13,280/day of a 500,000/month ≈ 16,600/day budget) as **"the
primary guard, not a nice-to-have."** Never measured until now, and B3 (this
session) changed the model in a way Part 1.4 did not anticipate.

## What B3 actually added, measured against the real database

Part 1.4's table costs every new v3.0 feature at 0–2 commands **per alert
run**. B3's retry/escalation writer does that too — but it also added a
`ZPOPMIN` call to `drain_due_retries()`, invoked on **every worker loop tick**,
independent of whether any alert has been dispatched. That is a cost that
scales with *wall-clock time the worker is running*, not with alert volume,
which is a new axis Part 1.4's model never had to account for.

**Per-alert-run cost, from real data** (33 real `alert.dispatched` events, not
assumed):

| Metric | Count | Rate |
|---|---|---|
| `delivery.retry_scheduled` events | 28 | **0.848 ZADD per dispatch** |
| `delivery.channel_escalated` events | 22 | **0.667 ZADD per dispatch** |

So each real dispatch now costs the spec's ~310 baseline **plus ≈1.5 ZADDs**,
not the 0–1 the original table assumed — a small, absorbable addition on its
own.

**Per-tick idle cost, from the code, not a run:** `due_delivery_ids()` issues
at least one `ZPOPMIN` per call even when the retry set is empty (it breaks on
the first empty pop), and the worker calls it every iteration of its main
loop — including the idle one, which fires every `delivery.xread_block_ms`
(seeded **5000 ms**). That is:

```
86,400,000 ms/day / 5,000 ms/tick = 17,280 ticks/day
17,280 ZPOPMIN calls/day, purely from being left running — before one alert fires
```

## Why that number is the actual finding

17,280 is **already above** the entire 16,600/day monthly-derived ceiling, and
nearly **1.3×** the Part 28 80% guard threshold (13,280) — from idle polling
alone, with zero alerts dispatched. A worker left running continuously for a
full day would exhaust the Upstash free tier's command budget on background
polling before doing any real work. This is not a demo-day risk in the "we
might run 53 alerts" sense Part 1.4 modelled — it is a **left-the-terminal-open**
risk, and given that `python run.py worker-cloud` is meant to be kept open for
the whole rehearsal/demo window (§6.14), it is the realistic failure mode.

## The fix — a config value, not a redesign

`delivery.xread_block_ms` is already an `app_config` row, not a literal in
code (Rule 1), so tuning it is a threshold change, not a rewrite. Raised from
**5,000 ms to 15,000 ms** — a 3× reduction in idle-tick frequency, applied via
`python run.py seed-config`:

| | Before | After |
|---|---|---|
| Idle ticks/day | 17,280 | **5,760** |
| Idle `ZPOPMIN` calls/day | 17,280 | **5,760** |
| Retry pickup latency (worst case) | 5 s | 15 s |

15 s of added worst-case retry latency is immaterial against the policy's own
`wait_before_next_s` values (45–120 s per step) — the schedule was never
sub-15-second precision in the first place.

## Revised worst case, with real rates and the fix applied

For a demo day with the worker running the full ~4-hour rehearsal-plus-live
window (14,400 s) and, generously, **10 real dispatch runs**:

| Source | Commands |
|---|---|
| Idle ticks (`14,400 s / 15 s`) | 960 × 1 ZPOPMIN = **960** |
| 10 dispatch runs × (310 baseline + 1.5 B3 average) | **3,115** |
| **Total** | **≈ 4,075** |

**4,075 / 16,600 ≈ 24.5% of the daily ceiling — 4.08× headroom**, short of the
stated **5×** target but not dangerously so, and computed from a genuinely
generous 4-hour continuous-run assumption. Running the worker only for the
actual demo slot (closer to 1–2 hours, per §10.5's script)
brings idle ticks down to 240–480 and total commands to ≈2,600–2,850, which
clears 5× headroom (16,600 / 5 = 3,320) with margin.

**Operational rule, not just an arithmetic footnote:** stop
`worker-cloud` between rehearsals rather than leaving it running across a full
day. The command cost is dominated by idle time, not alert volume, so the
single highest-leverage thing anyone can do for this budget is not open a
terminal and forget about it.

## What this does not cover

This re-derivation only prices `services/delivery/worker.py`'s own loop. It
does not re-derive the WebSocket ops-console cost (Part 13's 50-client target)
or the ingestion poller's cadence, neither of which changed today. A full
demo-day counter check per Part 28's runbook — reading Upstash's own usage
dashboard at T-30 min — is still the authoritative measurement and remains
unrun; this document is the *design* re-derivation the roadmap asked for, not
a substitute for checking the real dashboard before going live.

### 12.3 Four-tile DEM check — 21 Aug 2026

Part 19: *"The four-tile DEM check has a committed, dated pass/fail log."*
Part 29 names this exact check: `terrain_ruggedness` depends on exactly two
case-study districts (Wayanad, Palghar), whose centroids sit near four
candidate 1°×1° Copernicus GLO-30 tiles.

**Run with the AWS CLI, `--no-sign-request`, against the real S3 bucket** —
not simulated:

```bash
for tile in N11_00_E076_00 N19_00_E072_00 N19_00_E073_00 N11_00_E077_00; do
  aws s3 ls --no-sign-request \
    "s3://copernicus-dem-30m/Copernicus_DSM_COG_10_${tile}_DEM/" \
    && echo "OK: $tile" || echo "MISSING: $tile"
done
```

**One correction to Part 29's own literal command:** it writes the key as
`Copernicus_DSM_COG_30_{tile}_DEM`. The bucket is genuinely named
`copernicus-dem-30m`, but every object inside it uses `COG_10` in the key —
confirmed here by listing, and already recorded independently in this file's "Copernicus DEM tile keys are named `COG_10`, not
`COG_30`" note and used correctly in `scripts/fetch_data.sh`. Running Part 29's
literal command as written returns nothing and would be misread as all four
tiles missing, when they are all present.

## Result

| Tile | Covers | Status | `.tif` size |
|---|---|---|---|
| `N11_00_E076_00` | Wayanad (≈11.6°N, 76.1°E) | ✅ OK | 44,177,013 bytes |
| `N19_00_E072_00` | Palghar (≈19.7°N, 72.8°E) | ✅ OK | 13,336,459 bytes |
| `N19_00_E073_00` | Palghar's eastern neighbour cell | ✅ OK | 45,865,641 bytes |
| `N11_00_E077_00` | Wayanad's eastern neighbour cell | ✅ OK | 42,605,112 bytes |

**4/4 tiles present. No SRTM fallback needed for either case-study district.**
Every listing returned the real object (`Copernicus_DSM_COG_10_{tile}_DEM.tif`)
plus its `AUXFILES/`, `INFO/`, `PREVIEW/` sub-prefixes and companion `.xml` —
confirming these are genuine data objects, not empty placeholder prefixes.

## What this means downstream

`unit_features.terrain_ruggedness` and `mean_elevation_m` for Wayanad and
Palghar can be computed entirely from Copernicus GLO-30, with no per-cell SRTM
mixing required. If a future run against a different district set finds a
missing tile, mixing sources per-cell is still fine per Part 29 — ruggedness is
computed per admin-unit centroid, and each centroid falls in exactly one cell.

