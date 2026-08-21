# SETU — Current Tasks

Status-based, not day-based. Update this file whenever a task's status
changes — this is the file to open to answer "what do I do next."

For "how does the system work / why is it built this way," see
`docs/IMPLEMENTATION.md`, not this file.

**Legend:** 🔴 Blocked (needs an external account/credential/decision) ·
🟡 Ready to build (nothing blocking) · 🟢 Done · ⚪ Not started, not urgent

**Last verification (21 Aug 2026, line-by-line audit against Part 16):** **247 tests passed**, 2 skipped, delivery coverage **95.71%**. Live FCM credential authenticates against the real `setu-alerts` Firebase project; **live Twilio SMS proven end to end** — real `provider_accepted` (`twilio_sms_send`) followed by a real carrier callback writing `device_delivered` (`twilio_sms_webhook`) through an ngrok tunnel, HMAC-verified. Day-4 exit gate re-proven on a scratch DB: `upgrade head → downgrade 0006 → upgrade head` clean, and migration `0012` **fails loudly** with `PHONE_HASH_PEPPER` unset. `verify_seeds.py` now *fails* (not just reports) on empty `app_config` notes and on any alert with a NULL `incident_id`; both are at 0. Plus `test_officer_scope_covers_contained_village` (Vythiri officer → Muttil North 200; out-of-geom ADM5 403).

**Four real defects that audit found, all fixed:**
1. **`alert.approved` was never written to the ledger.** `services/governance/approvals.py` had no audit call at all, so F3 dual authorization — a below-the-cut-line feature — enforced the quorum but left no audit trace. Day 6's DoD names `alert.approved` as a required timeline entry.
2. **`alert.validation_failed` was never written either.** `POST /alerts/{id}/validate` persisted per-rule rows to `alert_validation_result` but appended no ledger entry, so a blocked dispatch (Day-9 run, step 3) was invisible in the timeline.
3. **`PGCRYPTO_SYM_KEY` did not exist** — absent from `.env`, `.env.example`, `gen_secrets.py` and `check_env_example.py`. `_encrypt_phone()` silently returned NULL, so **20 CSV-imported recipients had `phone_enc IS NULL`** and could never receive SMS/IVR/email. 4 recovered from `data/enrollment/team.csv`; **16 are unrecoverable** (source CSV gone, `phone_hash` is one-way).
4. **FCM sent a `notification` block on the webpush path**, which the browser tray consumes without ever running our service worker — so the receipt nonce never returned and the ladder could never advance past tier 1. Now data-only.

**Test gaps closed:** `geometry_non_empty` and `target_count_plausible` had no test in either direction (Day 5 wants all 6 rules with a passing *and* failing fixture); `GET /units/{id}/vulnerability`, `POST /response` and `POST /citizen/device` had no RBAC allow/deny pair (Day 10 wants one per Part 26 row); F4 had no "4th extreme is still delivered in full" test (Day 8). Citizen PWA signs in via `POST /api/v1/auth/login` (no pasted token). Officer scopes are assigned by name lookup (`python run.py provision-demo`). Console population/alerts/hazards are API-sourced; Compose does not default a severity. Model identities live in `app_config` (HF cards, registry names, versions). Shipping dedup is PostGIS spatial/temporal with measured P/R; MiniLM only vetoes a cluster when `/embed` returns real vectors. IndicTrans2 is registered only after a real `/translate` response. Reach-risk stays `is_bootstrap`. No invented translations or embeddings.

> A green test run is not the same as a working system. Everything above was
> re-verified against the real database and the real feeds, not from memory —
> and doing so surfaced five genuine bugs that all 37 tests then passing had passed over.
> See `docs/IMPLEMENTATION.md` §6.

---

## 🔴 Blocked — need an external account, credential, or decision

Firebase and Twilio credentials are **no longer blocking** — both are configured
and proven live (see the verification note above). What remains blocked needs a
**physical device, a second human, or an account we still do not have.**

| Task | Blocked on | Who |
|---|---|---|
| **Real FCM `provider_accepted`** | A real phone registering a push token. Needs the citizen PWA served over **HTTPS** — `getToken()` refuses a `http://192.168.x.x` origin, and `localhost` cannot be reached from a handset. `SELECT COUNT(*) FROM delivery_event WHERE source='fcm_send'` is still **0** | — |
| **Dev service-worker registration is broken** | `dev-sw.js` fails with "ServiceWorker script evaluation failed" on `python run.py citizen-dev`. **Pre-existing** — reproduced at the committed baseline, not caused by the FCM work. Blocks the SW receipt (rung 2) *and* the Gate-3 offline beat on the dev server. Production `dist/sw.js` builds fine, so `npm run preview` is the workaround | — |
| Real IVR call + DTMF (B6) | A human to answer a call and press digits. Voice costs several × an SMS — budget against the balance | — |
| Real B9 relay confirmation | Same. All 19 `relay_confirmation` rows are `method='http'`; the DTMF path writes `method='ivr_dtmf'` and has **never** run | — |
| Twilio webhook URLs not registered in the console | `sms-inbound` / `ivr-status` are not pointed at the tunnel, so E4's live `REGISTER` keyword cannot fire even though the tunnel is up and the code is done | — |
| More verified numbers | Only **1** verified caller ID (`+91…3529`). Spec wants 6–8 for demo beats + relay seeds. Verification is free; only sends cost | — |
| Relay-node seed data (live phones) | Twilio-verified numbers to replace `05_relay_nodes.sql` placeholder ciphertext | — |
| Email escalation channel (live) | Brevo or Resend API key in `.env` | — |
| Monitoring alerts | Discord/Slack incoming webhook URL | — |
| **Decision:** is B10 (Community Relay Mode) buildable? | ~20 min Web Bluetooth spike on two Android phones — see `docs/IMPLEMENTATION.md` §8.1 | — |
| **Decision:** where does production IndicTrans2 run? | Hugging Face Space (or other host) with `SETU_LOAD_ML_MODELS=1`. Local isolation is `python run.py ml` on :8001 | — |

**Ephemeral-tunnel caveat:** the free ngrok URL changes on restart, and
`PUBLIC_BASE_URL` plus every Twilio console webhook must be updated with it.
Before the demo this needs a static domain or the real Vercel/Render deploy.

## 🟡 Ready to build — nothing external blocking these

- [x] **`python run.py demo`** — Part 19 gate exists (`guard_local_only` → migrate → seed board if needed → load/verify snapshot). Needs local geometry; honcho is optional
- [ ] **Neon enrollment import** — `consented_recipients: 0` on Neon; `python run.py import-enrollment` now exits 1 if `data/enrollment/` has no CSV (will not invent recipients). Generate with `scripts/generate_enrollment_template.py` then fill real consented rows.
- [x] **C3 translation cache** — API writes `alert_translation` via HF Space `/translate` when `HF_SPACE_URL` is set; demo reads cache only; PWA/IVR/relay fall back with a visible notice. IndicTrans2 weights stay off the API process (`SETU_LOAD_ML_MODELS=1` on `services.ml.server` only)
- [x] **Dedup P/R on held-out set** — 200 labelled pairs in `data/ml/dedup_heldout.json`; shuffled 25% published to `model_registry` and Methodology
- [x] **axe-core on four new screens** — `web/console` `npm run test:a11y` reads TSX sources then runs axe; AssuranceLadder still announces “not applicable”
- [x] **Part 38 hardcoding three-pass** — Python AST + SQL VIEW comparisons + TS `relay`/`verify`/`response`/`sw`; `tests/unit/test_twiml_has_no_literals.py`
- [x] **Offline basemap extract** — `python run.py fetch-basemap` (go-pmtiles). Current extract is India bbox `68,6,98,38`, **maxzoom 6**, ~2.6 MB at `web/console/public/tiles/setu-basemap.pmtiles`. LiveMap attaches `earth`/`water`/`roads` after style load (a failed vector source cannot block the choropleth). Spec still wants Wayanad+Palghar z12; Gate 3 **cable-pull is unrehearsed**. Place-name glyphs use a CDN when online; village names are HTML labels and work without glyphs.
- [x] **Assign real `unit_scope_id` to officer accounts** — `python run.py provision-demo` ILIKE-looks up `demo.unit_scope.<email>` after geometry load (and at the end of `python run.py demo`). Seed SQL still leaves ids NULL on purpose.
- [x] **Citizen PWA login** — light sign-in against `POST /api/v1/auth/login`; session + refresh in `sessionStorage`. `VITE_CITIZEN_ACCESS_TOKEN` remains an override, not the demo path. Receipts stay nonce-gated. Dev server is **`:5174`** (`python run.py citizen-dev`); console is **`:5173`**.
- [x] **`python run.py ml`** — isolated `services.ml.server` on :8001. Weights load only if `SETU_LOAD_ML_MODELS=1` and the HF ids match. Production Space still 🔴.

## 🟢 Done

### Infrastructure & data

- [x] Repo initialized, `.gitignore`, venv on Python 3.12.1
- [x] `requirements.txt` pinned (169 packages, PyNaCl included, zero torch/transformers in API)
- [x] `infra/docker-compose.yml` — Postgres+PostGIS (port 5433), Redis, MailHog, all healthy
- [x] Migrations `0001`–`0012` written and applied; round-tripped clean (local + Neon schema)
- [x] Seed files `01`–`05` written and applied locally
- [x] Bootstrap scripts: `bootstrap_neon.py`, `bootstrap_local_data.py`, `env_loader.py`,
      `verify_data_layer.py`, `import_enrollment_csv.py`, `generate_enrollment_template.py`,
      `provision_demo_accounts.py`
- [x] `scripts/verify_seeds.py`, `doctor.py`, `gen_secrets.py`, `wait_for_db.py`, `guard_local_only.py`, `run.py`
- [x] Real local secrets generated — in `.env`, not committed
- [x] `docs/IMPLEMENTATION.md` and this file maintained
- [x] Data sources verified — `scripts/verify_data_sources.py`, 14/15 live
- [x] Admin-unit geometry loaded locally (8,302 rows ADM3+ADM5)
- [x] `safe_zone` (281 rows), population, terrain, relay nodes (6 rows, placeholder phones)
- [x] OpenCelliD — zero India rows documented honestly (§5.5 IMPLEMENTATION)
- [x] Neon cloud DB — full bootstrap complete (`verify_data_layer` clean): 8,302 units, 281 safe zones, 6 relay nodes. Refresh config with `python run.py neon-seed-config` (requires `.env.neon`)
- [x] **`app_config`** — operational thresholds keyed and noted, including `demo.citizen_email` / `demo.unit_scope.*` / `demo.password_emails`; refresh with `python run.py seed-config`
- [x] **`python run.py seed-config`** — idempotent upsert from `04_app_config.sql`
- [x] **`python run.py data-bootstrap`** — local migrate + config + enrollment CSV + verify
- [x] **Hardcoding policy enforced** — `check_no_hardcoding.py` three-pass (Python AST, SQL views, TS relay/verify/response/sw) +
      `check_pwa_config.py` (citizen PWA) + `test_twiml_has_no_literals.py`; all in CI

### Application — backend (roadmap Day 4–6 slice)

- [x] **Delivery core:** state machine, assurance, audit ledger, worker (Redis Streams),
      sim fallback when real adapters raise `ChannelUnavailable`
- [x] **Real channel adapters (env-gated):** FCM, SMS, IVR, email — fall back to sim when creds absent
- [x] **Twilio webhooks:** `sms-inbound`, `sms-status`, `ivr-status` (HMAC-verified)
- [x] **Alert signing:** Ed25519 in worker `build_message()`; public key via `GET /public/signing-key`
- [x] **Ingestion:** USGS + GDACS (SEARCH endpoint), poller/scheduler, normalize/persist,
      `incident_linker.py`, quarantine, fixtures
- [x] **Governance F1:** all 6 quality-gate rules + tests; state-keyed translation
- [x] **Governance F3:** approvals, quorum, authoritative auto-approve, property test
- [x] **Governance F2:** versioning, `POST /new-version`, supersede on dispatch, Redis lock
- [x] **Alert composer:** `POST /api/v1/alerts`, preview, validate, approve, dispatch
- [x] **C6 structured response** + **D11f assistance queue** + **D7f/D8f/D12f** unit endpoints
- [x] **D10f timeline** + **B8 assurance ladder** + receipts/ack
- [x] **F4 alert fatigue** wired into delivery worker
- [x] **E4 enrollment:** `phone_hash`, CSV dry-run → live import, SMS keyword handler,
      `POST /api/v1/admin/recipients/import`
- [x] **Public/citizen API:** `GET /public/config`, `GET /public/signing-key`,
      `GET /citizen/deliveries/{id}`
- [x] **CI:** `.github/workflows/ci.yml`, ruff, channel capability guard, 112 tests
- [x] **E1 RBAC (Part 26):** alerts + assistance + incidents + units + enrollment
      + citizen write paths. §12.2: auditor aggregate-only on assistance;
      relay_node never sees cases (count/area via `GET /assistance/summary`);
      receipts nonce-gated not role-gated. `assigned_by` taken from the token.

### Application — citizen PWA (`web/citizen/`)

- [x] Vite + React + Workbox (`injectManifest`, `src/sw.ts`)
- [x] Config from `GET /api/v1/public/config` — no hardcoded PWA timeouts, free-text cap, or C6 labels
- [x] Push → receipt; notification click → `notification_opened` + open delivery
- [x] Offline Background Sync for ack, response, receipt
- [x] UI: light-first, 18px body, 44px targets; Safe / Help equally weighted; help types from config
- [x] Location asked only for types in `response.location_prompt_types`; declining still files the case
- [x] Manual delivery ID entry (works without Firebase for dev/test)
- [x] `npm run build` passes · `python run.py citizen-dev` → `:5174`

### Application — operations console (`web/console/`)

- [x] Vite + React 19 + TS, dark-first, ~2,000 lines. Built to Part 0.4 / 0.5 / 11
      and **verified in a live browser against the running API**, not assumed —
      see `docs/IMPLEMENTATION.md` §7
- [x] Design tokens: exact 11.1 palette with measured contrast ratios recorded;
      angular corner-cut panels (`clip-path`, `border-radius: 0`); JetBrains Mono
      + `tabular-nums` on every number; glow on **extreme only**, suppressed
      under `prefers-reduced-motion` (all confirmed in the DOM)
- [x] **`AssuranceLadder`** — unprovable rungs struck through with the verbatim
      `not_applicable_reason` from the database + `sr-only` announcement.
      Verified live on a real siren delivery (3 struck rungs)
- [x] **`QualityGate`** — GitHub-PR-checks pattern, failing check named, reason
      adjacent to the disabled dispatch button, never a toast
- [x] **`ApprovalPanel`** — missing slot at FULL contrast, satisfied slot quiet
- [x] Command palette (`Ctrl+K`), login/JWT flow, Live Operations, Alert Detail, Assistance queue
- [x] Incident timeline (D10f), Command Board (D9f), Methodology — five event-time screens
- [x] WebSocket `/api/v1/ws/ops` + kill-feed rail on Live Operations
- [x] MapLibre live map with reachability choropleth; local Protomaps extract (`earth`/`water`/`roads`, India z6) so the pane is not a black box. Worker is `maplibre-gl/dist/maplibre-gl-worker.mjs?url` (Vite prebundle 404 otherwise). `.live-map { height: 520px }` is required — MapLibre's canvas is `position:absolute`, so a heightless wrapper collapses to 0px
- [x] **D1f is reachability, not a hazard overlay.** Active-alert polygons are not painted on Live Ops. The officer draws the area on Compose (A3). Incoming USGS/GDACS/nowcast/manual rows are the Live Ops table + Compose **Incoming sources** list (`GET /api/v1/alerts`)
- [x] **Scoped officer map is ADM5.** `GET /api/v1/ops/map` uses the officer's unit envelope, then the finest `admin_unit.level` in that envelope (villages for Vythiri). Features are clipped to the officer **geom**, not the bbox, so neighbouring taluks are not clickable. HTML labels name every village (cap 80). Nationwide/unscoped choropleth stays `map.geometry_level` (ADM3)
- [x] **Officer scope is geographic.** `admin_unit.parent_id` is NULL on all 8,302 rows, so the recursive `parent_id` walk never sees Muttil North under Vythiri. `assert_unit_in_scope` also allows `ST_Intersects(scope.geom, target.geom)`. `tests/unit/test_rbac.py::test_officer_scope_covers_contained_village` covers allow (8157) and deny (an ADM5 outside Vythiri)
- [x] **No fabricated population / alerts / hazards in the console.** Those figures render from the API (`v_reachability`, `alert`, officer-drawn GeoJSON). Compose does not default severity or headline; a village with NULL population shows "no population"
- [x] Optimistic UI banned — every mutation re-reads from the API
- [x] Two real bugs found by running it: ladder sampling buried the siren ladder;
      `SeverityBadge` rendered genuinely-unknown severity as "Minor" (§7.2)

## ⚪ Not started, lower priority for now

- [ ] Design tokens (`packages/tokens`) — currently console-local CSS matching Part 11.1
- [ ] B9 live Twilio relay call (adapter + DTMF path exist; needs verified numbers)
- [ ] B10 two-Android GATT demo (signing + PWA share path exist; Chrome has no GATT peripheral)
- [ ] 21-step recorded Gate 4 take
- [ ] Freeze demo + `nightly-20260821`; Days 12–13 rehearsal/load test
- [ ] Gate 3 cable-pull rehearsal (extract + HTML village labels are local; place-name glyphs still hit a CDN when online; `python run.py demo` then unplug)

---

## Roadmap position (spec Part 16)

Audited line by line on 21 Aug 2026 against the real system — DB, code and
tests — not against this file's own previous claims.

| Day | Theme | Status |
|---|---|---|
| Day 4 | Migrations, delivery core, F1, ingestion | ✅ **Exit gate re-proven.** Round-trip clean on a scratch DB; `0012` fails loudly without the pepper; `app_config` empty notes 0; NULL `incident_id` 0. All 6 F1 rules real. ⚠️ "real non-mock `provider_accepted`" is met for **SMS**, not FCM (`fcm_send` = 0) |
| Day 5 | F3, C6, D7f/D8f, B8 webhooks, E4 | ✅ All 6 rules now have pass+fail tests. **Real SMS → real `device_delivered`** via Twilio callback. D7f both denominators verified (unit 5179: 38.2% recipients / 1.5% population). Idempotency index + C6 CHECK constraint confirmed. ⚠️ Real push and real IVR still unproven |
| Day 6 | F2, D10f, citizen PWA, console, Gate 3 | ✅ `alert_one_active_per_incident_uix` + `audit_immutable` confirmed live. **`alert.approved` / `alert.validation_failed` now actually written** (they never were). D12f stores 7 named factors. ⚠️ Gate-3 cable-pull unrehearsed, and the dev SW is broken |
| Day 7 | D11f, E4, B10 transport, D13f | ✅ D11f stores all 5 factors + weights + `weight_version`. E4 rate-limited + HMAC-verified. D13f publishes p10/p50/p90 **and** `coverage_pct` + seismic exclusion reason. ⚠️ B10 two-device never run; live keyword blocked on console webhook config |
| Day 8 | F4, assignment, device decision, board data, snapshot | ✅ F4 **cannot** suppress by construction, now with the Day-8 test that proves it. Both `assistance_case` CHECKs confirmed. Board router has no business-logic literals. 24 snapshot tables |
| Day 9 | Gate 4 integration run | 🟡 Coverage gate **re-run and passing at 95.71%**. `authoritative_source` provenance present in `alert_approval`. **21-step recorded take not done** — needs 6 people + hardware |
| Day 10 | Command Board UI, after-action, RBAC, axe | ✅ `CommandBoard.tsx` grep clean. RBAC now **140 tests**, every Part 26 row with allow+deny. `npm run test:a11y` re-run → clean. Hardcoding guard confirmed to cover `governance/` + `response/` |
| Day 11 | Freeze | 🟡 `freeze-guard.yml` guards all Day-11 paths, epoch 21 Aug 21:00 IST. **Nightly tag not cut; repo has no tags at all.** Post-freeze block cannot be demonstrated until the epoch passes |
| Day 12–13 | Rehearsal | ⚪ Not started — every item needs humans or hardware |

---

## Quick commands

```powershell
python run.py db-up
python run.py seed-config          # refresh app_config from 04_app_config.sql
python run.py neon-seed-config     # same upsert against .env.neon
python run.py provision-demo       # unit_scope_id by name; SETU_DEMO_PASSWORD optional
python run.py verify-data          # admin units, config, recipients
python run.py data-bootstrap       # local full bootstrap
python run.py neon-bootstrap       # Neon: migrate + config + geometry
python run.py import-enrollment    # CSV dry-run then live (exits 1 if no CSV)
python run.py api                  # :8000
python run.py ml                   # isolated ML on :8001
python run.py worker
python run.py ingest
python run.py demo                 # Part 19 gate: load snapshot, provision scopes, then unplug
python run.py fetch-basemap        # Protomaps extract into web/console/public/tiles/
python run.py citizen-dev          # :5174 (console is :5173)
python -m pytest tests/ -q
python scripts/check_no_hardcoding.py
python scripts/check_pwa_config.py
```

---

## How to keep this file honest

- Move a task between sections the moment its status changes — don't batch updates.
- When something in 🔴 Blocked gets unblocked, move it to 🟡 and add a note in
  `docs/IMPLEMENTATION.md` if the unblocking taught us anything.
- If a task turns out to need something the design spec didn't anticipate, say so
  here in one line — don't silently absorb it.
