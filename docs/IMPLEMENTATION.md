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

### 3.4 Frontend — not yet started

Two apps planned: `web/console` (ops console, dark-first, dense) and
`web/citizen` (PWA, light-first, offline-capable). Directory skeletons exist;
no code yet.

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
not a one-off. Current result: **14/15 live, 0 failed, 1 skipped**
(OpenCelliD — needs `OPENCELLID_TOKEN`, not yet obtained; Part 30's
5-feature fallback applies until it clears).

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
| `04_app_config.sql` | every threshold, keyed and noted | 71 |
| `05_relay_nodes.sql` | 6 demo relay nodes — **currently placeholder ciphertext**, no-ops until `admin_unit` has Wayanad/Palghar rows | 0 (until geometry loads) |

`scripts/verify_seeds.py` asserts real counted minimums against the database
after seeding — **not** the design spec's prose numbers, which don't match
what the spec's own SQL produces once you count every `INSERT` tuple.

### 5.3 Known content gaps in the seed data

- `05_relay_nodes.sql` uses dummy `pgp_sym_encrypt('+91PLACEHOLDER...', 'CHANGE-ME')`
  values. Must be redone with real Twilio-verified team phone numbers before
  any human-relay (B9) work is tested, and it structurally cannot run until
  `admin_unit` contains the Wayanad/Palghar rows (which needs the ADM3/ADM5
  geometry load — not done yet).
- `quality_gate.required_lang_for_severe`/`_extreme` are keyed per state
  (`.KL` → `ml`, `.MH` → `mr`) rather than one global floor, because a single
  `'ml'` requirement would incorrectly gate Palghar (Maharashtra, Marathi)
  alerts.

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

Nothing has touched a cloud database yet — everything above is local Docker
only. The exact same migration round-trip needs to be re-run against Neon's
pooled + direct URLs once that account exists.

---

## 7. Repository layout

```
setu/
├── services/
│   ├── api/            settings.py (env config, Part 25-style)
│   ├── delivery/        channels/  (empty — adapters not written)
│   ├── ingestion/       adapters/  (empty)
│   ├── governance/      rules/     (empty)
│   ├── response/        (empty)
│   ├── enrollment/      (empty)
│   ├── ml/              (empty)
│   ├── audit/           (empty)
│   ├── crypto/          (empty — Ed25519 signing lives here, not written)
│   └── targeting/       (empty)
├── web/
│   ├── console/src/     (empty)
│   └── citizen/src/     (empty)
├── packages/tokens/src/ (empty)
├── data/
│   ├── seeds/           01-05 above
│   ├── snapshots/       (empty — no demo snapshot yet)
│   └── raw/             (gitignored — build-time downloads land here)
├── migrations/          alembic; versions/0001-0012 above
├── tests/                unit/ property/ contract/ integration/ e2e/ fixtures/  (all empty)
├── scripts/             gen_secrets.py, wait_for_db.py, guard_local_only.py,
│                        verify_seeds.py, doctor.py
├── infra/               docker-compose.yml
├── docs/                SETU_MASTER_v3.0_MERGED.md (design spec),
│                        IMPLEMENTATION.md (this file)
├── run.py               task runner (Makefile replacement)
├── requirements.txt      pinned, 169 packages
├── alembic.ini
└── .env.example
```
