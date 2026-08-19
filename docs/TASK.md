# SETU — Current Tasks

Status-based, not day-based. Update this file whenever a task's status
changes — this is the file to open to answer "what do I do next."

For "how does the system work / why is it built this way," see
`docs/IMPLEMENTATION.md`, not this file.

**Legend:** 🔴 Blocked (needs an external account/credential/decision) ·
🟡 Ready to build (nothing blocking) · 🟢 Done · ⚪ Not started, not urgent

**Last verification:** 76/76 pytest green (incl. 29 RBAC matrix tests) ·
**core loop proven end to end** — a severe alert now goes compose → quality
gate → two distinct approvals → dispatch → fan-out → worker → **241 delivered**
with a real assurance ladder (241 provider_accepted → 224 device_delivered)
and D7f reachability reporting **92.5% of registered recipients / 0.8% of
population**. Before this, every delivery in the system's history had failed ·
**authentication + RBAC live** — `POST /alerts/{id}/dispatch` went from
*200 with no token* to 401/403, and `approver_id` can no longer be supplied
by the caller · all four guards clean
(`check_no_hardcoding`, `check_channel_capability`, `check_env_example`,
`check_pwa_config`) · ruff clean on `services/` + `scripts/` + `tests/` ·
Docker stack healthy · **live USGS ingestion proven end-to-end** (3 real
earthquakes ingested from the live feed) · Rule 12 verified both ways on real
data (authoritative source auto-approves with zero human steps; human-composed
severe alert correctly blocked at 0/2) · audit ledger verified: 252 events,
zero broken hash links, `UPDATE audit_event` rejected by the Postgres trigger.

> A green test run is not the same as a working system. Everything above was
> re-verified against the real database and the real feeds, not from memory —
> and doing so surfaced five genuine bugs that all 37 tests then passing had passed over.
> See `docs/IMPLEMENTATION.md` §6.

---

## 🔴 Blocked — need an external account, credential, or decision

| Task | Blocked on | Who |
|---|---|---|
| Real push notifications (live FCM) | Firebase project + service-account JSON + **VAPID key pair** (web push certs) | — |
| Real SMS / IVR / human-relay calls | Twilio account + verified phone numbers (6–8 for demo beats + relay seeds) | — |
| Relay-node seed data (live phones) | Twilio-verified numbers to replace `05_relay_nodes.sql` placeholder ciphertext | — |
| Email escalation channel (live) | Brevo or Resend API key in `.env` | — |
| Monitoring alerts | Discord/Slack incoming webhook URL | — |
| **Decision:** is B10 (Community Relay Mode) buildable? | ~20 min Web Bluetooth spike on two Android phones — see `docs/IMPLEMENTATION.md` §8.1 | — |
| **Decision:** where does the ML service run? | Host that isolates `torch`/`transformers` from the API process | — |

## 🟡 Ready to build — nothing external blocking these

- [ ] **Neon enrollment import** — `consented_recipients: 0` on Neon; run `python run.py import-enrollment` when CSV is ready
- [ ] **Gate 3 offline rehearsal** — snapshot/demo-fixture tooling for disconnected demo
- [ ] **Finish RBAC across remaining routers** — auth + RBAC now exist
      (`services/api/{auth,rbac}.py`, migration `0013`, 29 tests) and are
      applied to `alerts.py`. Still to protect: `assistance`, `incidents`,
      `units`, `enrollment`, `response`, `ack`, `receipts`, `citizen`.
      The three §12.2 privacy rows live there and are the highest-value
      remaining work: **auditor = aggregate only** (never point geometry),
      **relay_node = never** (count and area, never a household list),
      **citizen = own data only**.
- [ ] **Assign real `unit_scope_id` to officer accounts** — the scoping
      helpers exist and are wired in, but seeded accounts are unscoped
      (`NULL`) because `admin_unit` ids are not stable across a geometry
      reload. Needs a lookup step at provisioning time. See
      `docs/IMPLEMENTATION.md` §6.10.
- [ ] **`services/ml`** — reach-risk / translation service (hosting TBD)

## 🟢 Done

### Infrastructure & data

- [x] Repo initialized, `.gitignore`, venv on Python 3.12.1
- [x] `requirements.txt` pinned (169 packages, PyNaCl included, zero torch/transformers in API)
- [x] `infra/docker-compose.yml` — Postgres+PostGIS (port 5433), Redis, MailHog, all healthy
- [x] Migrations `0001`–`0012` written and applied; round-tripped clean (local + Neon schema)
- [x] Seed files `01`–`05` written and applied locally
- [x] Bootstrap scripts: `bootstrap_neon.py`, `bootstrap_local_data.py`, `env_loader.py`,
      `verify_data_layer.py`, `import_enrollment_csv.py`, `generate_enrollment_template.py`
- [x] `scripts/verify_seeds.py`, `doctor.py`, `gen_secrets.py`, `wait_for_db.py`, `guard_local_only.py`, `run.py`
- [x] Real local secrets generated — in `.env`, not committed
- [x] `docs/IMPLEMENTATION.md` and this file maintained
- [x] Data sources verified — `scripts/verify_data_sources.py`, 14/15 live
- [x] Admin-unit geometry loaded locally (8,302 rows ADM3+ADM5)
- [x] `safe_zone` (281 rows), population, terrain, relay nodes (6 rows, placeholder phones)
- [x] OpenCelliD — zero India rows documented honestly (§5.5 IMPLEMENTATION)
- [x] Neon cloud DB — full bootstrap complete (`verify_data_layer` clean): 8,302 units, 118 config, 281 safe zones, 6 relay nodes
- [x] **`app_config` — 118 rows** (was 71); all operational thresholds keyed and noted
- [x] **`python run.py seed-config`** — idempotent upsert from `04_app_config.sql`
- [x] **`python run.py data-bootstrap`** — local migrate + config + enrollment CSV + verify
- [x] **Hardcoding policy enforced** — `check_no_hardcoding.py` (6 service dirs) +
      `check_pwa_config.py` (citizen PWA); both in CI

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
- [x] **CI:** `.github/workflows/ci.yml`, ruff, channel capability guard, 76 tests

### Application — citizen PWA (`web/citizen/`)

- [x] Vite + React + Workbox (`injectManifest`, `src/sw.ts`)
- [x] Config from `GET /api/v1/public/config` — no hardcoded PWA timeouts or free-text cap
- [x] Push → receipt; notification click → `notification_opened` + open delivery
- [x] Offline Background Sync for ack, response, receipt
- [x] UI: I'm safe / I need help / free-text other
- [x] Manual delivery ID entry (works without Firebase for dev/test)
- [x] `npm run build` passes · `python run.py citizen-dev` → `:5173`

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
- [x] Command palette (`Ctrl+K`), login/JWT flow, Live Operations, Alert Detail
- [x] Optimistic UI banned — every mutation re-reads from the API
- [x] Two real bugs found by running it: ladder sampling buried the siren ladder;
      `SeverityBadge` rendered genuinely-unknown severity as "Minor" (§7.2)

## ⚪ Not started, lower priority for now

- [ ] **Console screens 3–5** — Incident timeline (D10f), Assistance Queue
      (D11f), Command Board (D9f), Methodology. Part 0.4.3 names five
      event-time screens; two are built (§7.3)
- [ ] **D1f live map** — MapLibre + self-hosted `.pmtiles` (the offline beat
      depends on tiles being a file, not a request — spec §1.6.5)
- [ ] **WebSocket live feed** — console currently polls on load/refresh; Part 0.5's
      kill-feed rail is not built
- [ ] **`services/ml`** — no code, no hosting decision
- [ ] Design tokens (`packages/tokens`) — currently console-local CSS
- [ ] B9 human relay adapter (full flow — needs Twilio + real relay phones)
- [ ] B10 peer relay transport (needs Web Bluetooth spike)
- [ ] PDF audit report export

---

## Roadmap position (spec Part 16)

| Day | Theme | Status |
|---|---|---|
| Day 4 | Migrations, delivery core, F1, ingestion | ✅ Complete |
| Day 5 | F3, C6, D7f/D8f, B8 webhooks, E4 | ✅ Backend complete; live FCM/Twilio deferred |
| Day 6 | F2, D10f, citizen PWA, console, Gate 3 | 🟡 Citizen PWA + console (2 of 5 screens) done; Gate 3 pending |
| Day 7+ | Response loop, analytics, rehearsal | ⚪ Not started |

**When Firebase is ready:** drop service-account path in `.env` → real FCM + VAPID in citizen PWA.

---

## Quick commands

```powershell
python run.py db-up
python run.py seed-config          # refresh 118 app_config rows
python run.py verify-data          # admin units, config, recipients
python run.py data-bootstrap       # local full bootstrap
python run.py neon-bootstrap       # Neon: migrate + config + geometry
python run.py import-enrollment    # CSV dry-run then live
python run.py api                  # :8000
python run.py worker
python run.py ingest
python run.py citizen-dev          # :5173
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
