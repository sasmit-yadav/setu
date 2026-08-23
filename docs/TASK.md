# SETU — Current Tasks

Status-based, not day-based. Update this file whenever a task's status
changes — this is the file to open to answer "what do I do next."

For "how does the system work / why is it built this way," see
`docs/IMPLEMENTATION.md`, not this file. Product docs under `docs/` are
only this file, `IMPLEMENTATION.md`, and `SETU_MASTER_v3.0_MERGED.md`.

**Legend:** 🔴 Blocked (needs an external account/credential/decision) ·
🟡 Ready to build (nothing blocking) · 🟢 Done · ⚪ Not started, not urgent

**Last verification (22 Aug 2026 — SIH live Extreme on Neon, then desk copy):**
Prior suite on 21 Aug: **267 tests passed**, 2 skipped, delivery coverage
**95.87%**, all six guards green, `ruff check services/` clean. 22 Aug added
`test_officer_assistance_lists_contained_village` and the Extreme
multi-channel worker path. Full write-up: `docs/IMPLEMENTATION.md` **§6.18**
(what Neon held) and **§7.6** (Help needed ≠ Send a runner).

**Now running in production** on four free-tier services at ₹0 —
PWA https://setucitizen.vercel.app · console https://setuconsole.vercel.app ·
API https://setu-api-6ujx.onrender.com · Neon · Upstash. Verified against the
live stack, not assumed: real login → JWT, `/auth/me` returning the
correct officer scope, 39 PostGIS village features clipped to Vythiri, `sw.js`
served as `application/javascript`, CORS admitting the Vercel origins, and the
laptop worker consuming Upstash. Topology: §6.14. Citizen village inbox
(no typed delivery ID): §6.16. Live Extreme: §6.18.

✅ **`fcm_send` is proven.** Live Extreme **alert 6** wrote real
`provider_accepted` FCM rows for Muttil recipients 1, 3, and 4. Recipient 5’s
token was `device_unregistered` (honest fail, not simulated). Enable alerts
again on that PWA before the next Send.

**Demo-day now (22 Aug, this laptop).** The loop works. What still kills a
stage run is operational, not missing code:

1. **Worker is up** — `python run.py worker-cloud` against `.env.cloud`
   (Neon + Upstash + FCM + Twilio). Leave that terminal open. Sleep = silent
   queue. Set `PYTHONIOENCODING=utf-8` on Windows or a log line can kill the
   process. Render’s worker service stays **suspended**.
2. **Do not Send alert 6 again.** It is already active Extreme on Muttil
   North. A second Send fans out more Twilio minutes and another IVR blast.
3. **Help needed ≠ Send a runner.** Help needed is `assistance_case`
   (someone asked for rescue). Send a runner is `human_relay` (the village
   never got the warning). Ack / “Opened or answered” is not a reply.
4. **Help while online is honest.** A failed Help POST says it was not
   sent — tap again. Airplane mode shows the cached copy, not a fake
   pending queue. See §10.5.
5. **Hosted desk may still look like the old topbar** until the §7.6 files
   are on `main` and Vercel Root Directory is `web/console`. Hard-refresh
   after that deploy.
6. **Trial IVR:** callee presses **any key** for Twilio’s trial lady, **then**
   1 (safe) / 2 (help).
7. **Citizen APK ≠ Chrome PWA.** Sideload
   `mobile/citizen-apk/dist/SETU-citizen.apk` for a home-screen icon
   (login survives app close). Enable alerts / Gate 3 still need
   **Android Chrome → Add to Home Screen**. Push inside the WebView APK
   is not a claim we can make. §7.7.

### 23 Aug — SIH internal presentation (what is still loose)

**Spoken 10-minute pitch** (mapped to `docs/SETU_SIH2026_Idea_FINAL.pdf`):
`docs/PITCH.md`. Rehearse §A out loud once. Do not read IMPLEMENTATION
on stage.

The stack is live. Do **not** spend the morning writing new features.
Rehearse the operational loop and name the gaps out loud. Skip list is
the cut order, not shame:

| Show | Skip / say so |
|---|---|
| Officer A/B Two-Eyes on a **new** Muttil warning (not alert 6) | Do not Send alert 6 again |
| Citizen OTP / email login, village inbox, Safe + Help | Typed delivery ID |
| SMS + IVR on the four verified SIMs (trial any-key then 1/2) | Nationwide SMS (no TRAI DLT) |
| FCM after **Enable alerts** in Chrome PWA | FCM inside the sideload APK |
| Help needed = trapped person; Give to team on the row | On foot as if it were the same queue |
| Struck-through ladder rungs with the seeded reason | A flattering “88% delivered” |
| Malayalam if `alert_translation` already has the row | Live HF Space / IndicTrans2 on stage |

⛔ **A new Kerala Extreme cannot be Sent.** `translation_exists` is a hard
**fail**, not a warn, and it is keyed by `alert_id`: a Kerala severe/extreme
needs an `alert_translation` row in `ml` *for that alert*. A brand-new alert
has none, no working model exists to write one, and reusing alert 6's exact
wording does not help because the row is keyed by id, not by text. Either
hand-enter the Malayalam for the new alert before Validate — and say on stage
that it is pre-entered, not model output — or re-Send alert 6, which this file
forbids. Decide before the room, not in it.

### Siren and peer relay — both demoable, 22 Aug

**The siren was never a stub.** `WebhookSirenAdapter` is a real HTTP client;
the seed ships `config = '{}'` for the siren row, so the URL fell back to the
API root, every POST 404'd, and every siren delivery landed on the simulated
path. Two changes on Neon (not in git — they point at a laptop):

```sql
UPDATE channel SET config = '{"webhook_url":"http://127.0.0.1:9099/siren"}'::jsonb
 WHERE code = 'siren';
INSERT INTO recipient (unit_id, kind, preferred_lang, consented_at, consent_source)
VALUES (8157, 'village_siren', 'ml', now(), 'panchayat_device_registration');
```

The recipient has no phone and no push token, so `resolve_channels_for_recipients`
walks the extreme policy past fcm/sms/ivr and lands on `siren` — an AREA
channel, always addressable. Verified: recipient 12 resolves to
`siren simulated=False`, and the adapter POSTing real Neon config to the
listener returned `provider_ref=siren-0, simulated=False`.

Run `python scripts/siren_listener.py` (drop `--silent` for audio) and keep
the terminal visible. The ladder still strikes device_delivered / opened /
acknowledged, because the adapter declares it cannot prove them — a siren
cannot tell you anyone heard it.

**Peer relay needs no code.** `relay.ts` does attempt real Web Bluetooth
GATT as a *central*; what a browser cannot do is *advertise* as a peripheral.
So phone-to-phone browser BLE is out, but browser → a real peripheral works
today. Point any GATT server (nRF Connect on a spare Android, an ESP32) at
service `8e7f3c10-5a2b-4d91-9c4e-1f2a3b4c5d6e`, characteristic
`...5d6e` ending `11`, 480-byte chunks, and Share reports "Shared over
Bluetooth." With no hardware, `sharePeer` also posts to a `BroadcastChannel`
— two tabs of the PWA side by side show the PEER badge after the Ed25519
check, which is the actual claim being made.

**Loose ends that can still kill the room** — all operational, all in
this file’s 🔴/🟡:

1. **`worker-cloud` terminal open**, `PYTHONIOENCODING=utf-8`, laptop
   awake. Sleep = silent queue. Render worker stays suspended.
2. **Recipient 5’s FCM token is dead.** Enable alerts on the presenting
   Chrome PWA *before* the first Send of the day.
3. **PWA “Pending” is often a lie.** If Help needed stays empty after
   ack, tap Help again — do not wait for “as soon as there is a signal.”
   🟡 still unfixed.
4. **Hosted console** must be the §7.6 desk (Help needed vs Send a
   runner). Confirm Vercel Root Directory is `web/console` and
   hard-refresh. If it looks like the old topbar, the judges see the
   confusion we already had.
5. **Deploy `web/citizen` `localStorage` to Vercel** so the *website*
   also survives a close. The APK shim covers the current bundle; the
   hosted tab does not until that deploy.
6. **Gate 3 cable-pull is unrehearsed.** Caching works; the physical
   unplug has never been done. Either rehearse 10 min the night before
   or drop it from the script.
7. **Send a runner stays empty** unless a `human_relay` row exists.
   Simulated siren on recipient 5 counted as delivered, so the chain
   never opened a runner. Do not click On foot expecting the trapped
   person. 🟡 auto-human-relay still unfixed — plant a pending runner
   task if you need that screen.
8. **Two-phone BLE (B10)** is probably impossible in a browser (§8.1).
   Do not budget it for the morning. Signing + provenance chip exist;
   say “one hop, not a mesh, Chromium-only” and move on.
9. **Render cold start ~50 s** if the API slept 15 min. Hit `/health`
   before anyone sits down. Keepalive workflow needs repo secrets
   `API_URL` / `HF_SPACE_URL` — Space URL is still missing.
10. **Twilio trial cap is 5 verified numbers.** Do not add a sixth.
    Credit is finite; every extra Send burns minutes.
11. **Dual-auth on two physical devices** and the **21-step recorded
    take** have never been rehearsed. Internal presentation can show
    the 409 `{have:1,need:2}` on one laptop + second login; do not
    promise the choreographed 10× run.
12. **Other villages** may show `consented_recipients: 0`. Muttil North
    (8157) is the only live enrollment. Draw Muttil, not a random ADM3.

Do this for a *new* warning only: citizen **Enable alerts** → officer A/B
**Extreme on Muttil North** (en+ml, Two-Eyes) → worker sends SMS+IVR to every
numbered phone and FCM when a token exists. Skip siren hardware, two-phone
BLE, HF Space, cable-pull unless rehearsed. `ml-load` is optional if Malayalam is already in
`alert_translation`.

Live FCM authenticates against `setu-alerts`. **Live Twilio SMS + IVR proven
end to end** on alert 6 (real SIDs, not simulated), including **IVR DTMF 1 =
SAFE** and a later **PWA trapped** that opened `assistance_case` 1. Day-4
exit gate was re-proven on 21 Aug on a scratch DB: `upgrade head → downgrade
0006 → upgrade head` clean, and migration `0012` **fails loudly** with
`PHONE_HASH_PEPPER` unset. `verify_seeds.py` *fails* (not just reports) on
empty `app_config` notes and on any alert with a NULL `incident_id`. Plus
`test_officer_scope_covers_contained_village` and
`test_officer_assistance_lists_contained_village` (Vythiri officer → Muttil
North 200; out-of-geom ADM5 403).

**Six real defects the line-by-line Part 16 audit found, all fixed** (full write-up in `docs/IMPLEMENTATION.md` §6.13):

0. **B3 — policy-driven retry + channel escalation — was never implemented.** `escalation_policy.wait_before_next_s` / `backoff_multiplier` / `jitter_ms` / `max_attempts` were seeded per severity and read by **no code at all**; grepping the whole tree found them only in the migration and the seed file. Every one of 1,987 deliveries was `attempt = 1`, the `escalated` state had **zero** rows, and 462 failures were abandoned after a single try on a single channel — a transient provider hiccup was a *permanent* failure on the primary channel. It also broke B9: `on_channels_exhausted()` fired on the *first* `ChannelUnavailable`, so "every digital channel is gone" was true of one attempt on one channel, spending the most expensive channel in the table (`cost_weight` 12) on a hiccup. Now driven by the policy — 30 deliveries have reached attempt 2 and `escalated` holds 12 rows. `[C]` core Module B.
1. **`alert.approved` was never written to the ledger.** `services/governance/approvals.py` had no audit call at all, so F3 dual authorization — a below-the-cut-line feature — enforced the quorum but left no audit trace. Day 6's DoD names `alert.approved` as a required timeline entry.
2. **`alert.validation_failed` was never written either.** `POST /alerts/{id}/validate` persisted per-rule rows to `alert_validation_result` but appended no ledger entry, so a blocked dispatch (Day-9 run, step 3) was invisible in the timeline.
3. **`PGCRYPTO_SYM_KEY` did not exist** — absent from `.env`, `.env.example`, `gen_secrets.py` and `check_env_example.py`. `_encrypt_phone()` silently returned NULL, so **20 CSV-imported recipients had `phone_enc IS NULL`** and could never receive SMS/IVR/email. 4 recovered from `data/enrollment/team.csv`; **16 are unrecoverable** (source CSV gone, `phone_hash` is one-way).
4. **FCM sent a `notification` block on the webpush path**, which the browser tray consumes without ever running our service worker — so the receipt nonce never returned and the ladder could never advance past tier 1. Now data-only.

**Test gaps closed:** B3 growth/jitter/escalation (16 tests, plus the captured backoff log in `docs/IMPLEMENTATION.md` §12.1); `STOP`/`opted_out_at` had **no test at all** despite being a consent guarantee; `geometry_non_empty` and `target_count_plausible` had no test in either direction (Day 5 wants all 6 rules with a passing *and* failing fixture); `GET /units/{id}/vulnerability`, `POST /response` and `POST /citizen/device` had no RBAC allow/deny pair (Day 10 wants one per Part 26 row); F4 had no "4th extreme is still delivered in full" test (Day 8). Citizen PWA signs in via `POST /api/v1/auth/login` (no pasted token). Officer scopes are assigned by name lookup (`python run.py provision-demo`). Console population/alerts/hazards are API-sourced; Compose does not default a severity. Model identities live in `app_config` (HF cards, registry names, versions). Shipping dedup is PostGIS spatial/temporal with measured P/R; MiniLM only vetoes a cluster when `/embed` returns real vectors. IndicTrans2 is registered only after a real `/translate` response. Reach-risk stays `is_bootstrap`. No invented translations or embeddings.

> A green test run is not the same as a working system. Everything above was
> re-verified against the real database, the real feeds and real providers —
> not from memory. Two separate audits have now proved the point: five bugs
> found while 37 tests were green (§6.12), and six more while 219 were green
> (§6.13). Both times the suite passed because no test asserted on the
> *consequence* — the ledger after approving, the attempt column after a
> failure, the cache after a page load.

---

## 🟢 DEPLOYED — live URLs

| Component | Host | URL |
|---|---|---|
| Citizen PWA | Vercel | https://setucitizen.vercel.app |
| Officer console | Vercel | https://setuconsole.vercel.app |
| API | Render free web | https://setu-api-6ujx.onrender.com |
| Postgres + PostGIS | Neon (Singapore) | at `0016`, 8,302 units, 5 Muttil North recipients (4 phones + 1 PWA) |
| Redis Streams | Upstash (Singapore) | probe read + acked |
| Delivery worker | **local** → cloud | `python run.py worker-cloud` |
| ML / translations | HF Space | ❌ not deployed |

**Total cost: ₹0.** Full write-up and the nine deployment failures in
`docs/IMPLEMENTATION.md` §6.14; step-by-step runbook in §10 of the same file.

⚠️ **The worker runs on a laptop.** Render's free tier has no background
workers, so `setu-worker` is suspended there. Keep the `worker-cloud` terminal
open during any demo — it is the process that actually sends. If the laptop
sleeps, dispatch enqueues and nothing sends.

---

## 🔴 Blocked — needs a device, a human, or an account

Firebase, Twilio, Neon, Upstash, Render and Vercel are all configured and
verified. What remains needs something no amount of code can supply.

| Task | Blocked on | Effort |
|---|---|---|
| Gate 3 cable-pull | Install to home screen, airplane mode, reopen. Caching is verified working; the physical beat is unrehearsed | 10 min |
| Real B9 relay confirmation via **IVR DTMF** | HTTP confirm exists and was used. All prior `relay_confirmation` rows were `method='http'`; the `ivr_dtmf` runner path has **never** run | 15 min |
| Twilio console webhooks | Point `sms-inbound` / `sms-status` at the Render URL (status may already be ngrok/local). Until Render is the inbound URL, live `REGISTER` from SMS cannot fire in production | 2 min |
| Worker not hosted | Render Starter ≈ $7/mo, or fold the consumer into the API process. Laptop `worker-cloud` is the demo path | decision |
| Real translations hosted (C3) | HF Space with `SETU_LOAD_ML_MODELS=1`. **The model has never run here** — checked 22 Aug: 0 of 3 `alert_translation` rows carry a `model_id`, IndicTrans2 is absent from `model_registry` (it self-registers only on a real `/translate`), the weights are not in the HF cache, there is no `.venv-ml`, and `HF_SPACE_URL` is empty in `.env.cloud`. Alert 6's Malayalam was entered by hand. **This blocks a new Kerala Extreme** — see the 23 Aug note | 45–90 min |
| Monitoring | `SLACK_OR_DISCORD_ALERT_WEBHOOK` is empty. Nothing reports the worker dying | 5 min |
| Email channel | Brevo or Resend API key | 5 min |
| **Decision:** is B10 buildable as Bluetooth? | No browser GATT peripheral. Demo path is a signed `?peer=` URL (§8.1, §10.5). Native BLE is still cut-order #4 | done (URL fallback) |

**Unblocked 22 Aug (do not put these back in 🔴):**

- Real FCM `provider_accepted` (`fcm_send`) on alert 6 recipients 1, 3, 4.
- Real IVR call + DTMF 1 (SAFE) on alert 6 delivery 8.
- Four Twilio trial verified numbers (`+917988243529`, `+919711117266`,
  `+918797975654`, `+919319277596`). Trial cap is 5; do not add more
  without a paid number.
- Citizen sideload APK (`python run.py citizen-apk`). Session survives
  app close. Push still Chrome PWA, not the WebView.

**Artifacts that looked blocked and are not:**

- Four-tile DEM log — `docs/IMPLEMENTATION.md` §12.3 (Part 19 #25).
- Redis command-budget — `docs/IMPLEMENTATION.md` §12.2, **4.08×**
  not 5× (Part 19 #12). Stop the worker between rehearsals; idle `ZPOPMIN`
  is the cost.

### Known data loss, unrecoverable

16 CSV-imported recipients have `phone_enc IS NULL` from the missing
`PGCRYPTO_SYM_KEY` (§6.13). Their source CSV is deleted and `phone_hash` is a
one-way HMAC, so the numbers cannot be recovered — they must be re-enrolled from
whatever original list they came from.

## 🟡 Ready to build — nothing external blocking these

- [x] **`python run.py demo`** — Part 19 gate exists (`guard_local_only` → migrate → seed board if needed → load/verify snapshot). Needs local geometry; honcho is optional
- [ ] **PWA help POST honesty** — `web/citizen/src/App.tsx` `sendResponse` treats `TypeError` as offline and paints “Saved. Will send as soon as there is a signal” with **no in-page queue**. Ack can succeed and Help needed stay empty. Retry + honest error; do not claim queued. §6.18
- [ ] **Auto `human_relay` when siren is simulated** — recipient 5’s simulated siren counted as delivered, so `on_channels_exhausted` never opened a runner task. Extreme should still spend a human when the last *real* channel failed. §6.18
- [ ] **Neon enrollment import** — Muttil has 5 live recipients; other villages may still show `consented_recipients: 0`. `python run.py import-enrollment` exits 1 if `data/enrollment/` has no CSV. Generate with `scripts/generate_enrollment_template.py` then fill real consented rows.
- [ ] **C3 translation cache** (path built, model never run) — API writes `alert_translation` via `/translate` when `HF_SPACE_URL` is set; PWA/IVR/relay fall back with a visible notice. Weights stay off the API (`SETU_LOAD_ML_MODELS=1` only on `services.ml.server`). Space still not deployed — laptop path is `python run.py ml-load` plus `worker-cloud` / `translate-cloud` (defaults `HF_SPACE_URL` to `:8001`). Server now uses IndicTransToolkit + FLORES tags; raw `generate()` was not Malayalam. Alert 6's `en` is the source text and its `ml` row was hand-entered — `model_id` is NULL on both, so nothing here is model output.
- [x] **Dedup P/R on held-out set** — 200 labelled pairs in `data/ml/dedup_heldout.json`; shuffled 25% published to `model_registry` and Methodology
- [x] **axe-core on four new screens** — `web/console` `npm run test:a11y` reads TSX sources then runs axe; AssuranceLadder still announces “not applicable”
- [x] **Part 38 hardcoding three-pass** — Python AST + SQL VIEW comparisons + TS `relay`/`verify`/`response`/`sw`; `tests/unit/test_twiml_has_no_literals.py`
- [x] **Offline basemap extract** — `python run.py fetch-basemap` (go-pmtiles). Current extract is India bbox `68,6,98,38`, **maxzoom 6**, ~2.6 MB at `web/console/public/tiles/setu-basemap.pmtiles`. LiveMap attaches `earth`/`water`/`roads` after style load (a failed vector source cannot block the choropleth). Spec still wants Wayanad+Palghar z12; Gate 3 **cable-pull is unrehearsed**. Place-name glyphs use a CDN when online; village names are HTML labels and work without glyphs.
- [x] **Assign real `unit_scope_id` to officer accounts** — `python run.py provision-demo` ILIKE-looks up `demo.unit_scope.<email>` after geometry load (and at the end of `python run.py demo`). Seed SQL still leaves ids NULL on purpose.
- [x] **Citizen PWA login** — light sign-in against `POST /api/v1/auth/login`; session + refresh in **`localStorage`** (migrates leftover `sessionStorage` on first load so a closed APK / installed PWA stays signed in). Hosted path is OTP (`/auth/citizen/otp/request|verify`). `VITE_CITIZEN_ACCESS_TOKEN` remains an override, not the demo path. Receipts stay nonce-gated. Dev server is **`:5174`** (`python run.py citizen-dev`); console is **`:5173`**. Sideload APK: `python run.py citizen-apk`.
- [x] **`python run.py ml`** — isolated `services.ml.server` on :8001. Weights load only if `SETU_LOAD_ML_MODELS=1` and the HF ids match. Production Space still 🔴.

## 🟢 Done

### Infrastructure & data

- [x] Repo initialized, `.gitignore`, venv on Python 3.12.1
- [x] `requirements.txt` pinned (169 packages, PyNaCl included, zero torch/transformers in API)
- [x] `infra/docker-compose.yml` — Postgres+PostGIS (port 5433), Redis, MailHog, all healthy
- [x] Migrations `0001`–`0016` written and applied; round-tripped clean (local + Neon schema; 0015 citizen OTP, 0016 reachability excludes sim)
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
      sim fallback when real adapters raise `ChannelUnavailable`. Extreme Send
      inserts SMS+IVR for every numbered phone and FCM when a token exists;
      `process_recipient` sends **every** pending channel, not `LIMIT 1`. FCM
      `device_unregistered` fails honestly (never simulated). Windows worker
      needs `PYTHONIOENCODING=utf-8` (§6.18)
- [x] **Ack ≠ reply ≠ Help needed.** `POST /ack` is a receipt.
      `citizen_response` is the human answer. `assistance_case` opens only for
      help types. SAFE (IVR 1 / PWA Safe / SMS SAFE) does not open a case.
      Extreme sends SMS+IVR+FCM at once; **Severe uses the same channels but
      waits** (`escalation_policy.wait_before_next_s`) between them.
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
- [x] Offline Background Sync for ack, response, receipt — **the in-page “Pending” banner is still a lie** when `POST /response` fails online (🟡 above)
- [x] UI: light-first, 18px body, 44px targets; Safe / Help equally weighted; help types from config
- [x] Location asked only for types in `response.location_prompt_types`; declining still files the case
- [x] Village inbox without a typed delivery ID (OTP / email login). Manual ID remains a fallback, not the demo path.
- [x] Sideload APK of the hosted PWA (`mobile/citizen-apk/`, not Play Store). Login persists across app close. Enable alerts is still Chrome.
- [x] `npm run build` passes · `python run.py citizen-dev` → `:5174`

### Application — operations console (`web/console/`)

- [x] Vite + React 19 + TS, dark-first. Built to Part 0.4 / 0.5 / 11
      and **verified in a live browser against the running API**, not assumed —
      see `docs/IMPLEMENTATION.md` §7 and **§7.6** (22 Aug readable desk)
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
- [x] **Officer scope is geographic.** `admin_unit.parent_id` is NULL on all 8,302 rows, so the recursive `parent_id` walk never sees Muttil North under Vythiri. `assert_unit_in_scope` **and** `list_cases` / `GET /assistance/summary` allow `ST_Intersects(scope.geom, target.geom)`. Neon row 8157 was also parented to 3081 so the already-deployed Render query could see case 1. `tests/unit/test_rbac.py::test_officer_scope_covers_contained_village` and `test_officer_assistance_lists_contained_village` cover allow (8157) and deny (an ADM5 outside Vythiri)
- [x] **Help needed vs Send a runner.** Queue types the team on the row; runner empty-state is honest; Live Ops ack KPI is “Opened or answered”; ReplyInbox is three KPIs. Hosted Vercel needs a push of those files (§7.6)
- [x] **No fabricated population / alerts / hazards in the console.** Those figures render from the API (`v_reachability`, `alert`, officer-drawn GeoJSON). Compose does not default severity or headline; a village with NULL population shows "no population"
- [x] Optimistic UI banned — every mutation re-reads from the API
- [x] Two real bugs found by running it: ladder sampling buried the siren ladder;
      `SeverityBadge` rendered genuinely-unknown severity as "Minor" (§7.2)

## ⚪ Not started, lower priority for now

- [ ] Design tokens (`packages/tokens`) — currently console-local CSS matching Part 11.1
- [ ] B9 live Twilio relay **DTMF** confirm (HTTP confirm exists; `ivr_dtmf` path unused)
- [ ] B10 two-Android GATT demo (signing + PWA share path exist; Chrome has no GATT peripheral)
- [ ] 21-step recorded Gate 4 take
- [ ] Freeze demo + `nightly-20260821`; Days 12–13 rehearsal/load test
- [ ] Gate 3 cable-pull rehearsal (extract + HTML village labels are local; place-name glyphs still hit a CDN when online; `python run.py demo` then unplug)

---

## Roadmap position (spec Part 16)

Audited line by line on 21 Aug 2026 against the real system — DB, code and
tests — not against this file's own previous claims. **22 Aug live Extreme
(alert 6) is recorded in §6.18**; Day 4/5 footnotes below were updated that
day so they do not still say FCM and IVR are unproven.

| Day | Theme | Status |
|---|---|---|
| Day 4 | Migrations, delivery core, F1, ingestion | ✅ **Exit gate re-proven 21 Aug.** Round-trip clean on a scratch DB; `0012` fails loudly without the pepper; `app_config` empty notes 0; NULL `incident_id` 0. All 6 F1 rules real. **22 Aug:** real non-mock `provider_accepted` is met for **SMS, IVR, and FCM** on alert 6 |
| Day 5 | F3, C6, D7f/D8f, B8 webhooks, E4 | ✅ All 6 rules now have pass+fail tests. **Real SMS → real `device_delivered`** via Twilio callback. **B3 retry/escalation now actually runs** (was dead code — see §6.13). D7f both denominators verified (unit 5179: 38.2% recipients / 1.5% population). Idempotency index + C6 CHECK constraint confirmed. **22 Aug:** real push (`fcm_send`) and real IVR + DTMF 1 proven on alert 6. B9 `ivr_dtmf` *relay confirm* still unused |
| Day 6 | F2, D10f, citizen PWA, console, Gate 3 | ✅ `alert_one_active_per_incident_uix` + `audit_immutable` confirmed live. **`alert.approved` / `alert.validation_failed` now actually written** (they never were). D12f stores 7 named factors. **Gate-3 offline caching now works on the dev server** (SW fix). ⚠️ Physical cable-pull still unrehearsed |
| Day 7 | D11f, E4, B10 transport, D13f | ✅ D11f stores all 5 factors + weights + `weight_version`. E4 rate-limited + HMAC-verified, and `STOP` → `opted_out_at` → never-enqueued is now tested end to end. D13f publishes p10/p50/p90 **and** `coverage_pct` + seismic exclusion reason. ⚠️ B10 two-device never run; live keyword blocked on console webhook config |
| Day 8 | F4, assignment, device decision, board data, snapshot | ✅ F4 **cannot** suppress by construction, now with the Day-8 test that proves it. Both `assistance_case` CHECKs confirmed. Board router has no business-logic literals. 24 snapshot tables, final snapshot cut |
| Day 9 | Gate 4 integration run | 🟡 Coverage gate **re-run and passing at 95.87%** (up from 95.71% with B3's tests). `authoritative_source` provenance present in `alert_approval`. Retry-backoff evidence artifact committed. **21-step recorded take not done** — needs 6 people + hardware |
| Day 10 | Command Board UI, after-action, RBAC, axe | ✅ `CommandBoard.tsx` grep clean. RBAC now **140 tests**, every Part 26 row with allow+deny. `npm run test:a11y` re-run → clean. Hardcoding guard confirmed to cover `governance/` + `response/` |
| Day 11 | Freeze | 🟡 `freeze-guard.yml` guards all Day-11 paths, epoch 21 Aug 21:00 IST. Final snapshot committed ✅ (and re-cut after 69 fabricated translations were purged from it), `nightly-20260821` tag cut ✅, Part 19 walked ✅ (`docs/IMPLEMENTATION.md` §11). Post-freeze block cannot be demonstrated until the epoch passes |
| — | **Deploy** *(not a roadmap day)* | ✅ Vercel + Render + Neon + Upstash live at ₹0, verified end to end. Worker runs locally (`worker-cloud`) because Render free has no background workers. HF Space not deployed, and `ml-load` has never actually run — no translation in this database carries a `model_id` |
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
python run.py ml                   # isolated ML on :8001 (weights off)
python run.py ml-load              # same, WITH IndicTrans2 weights (keep open)
python run.py translate-cloud      # fill Neon alert_translation via local :8001
python run.py worker             # local DB + local Redis
python run.py worker-cloud       # local process, DEPLOYED Neon + Upstash (.env.cloud)
python run.py ingest
python run.py demo                 # Part 19 gate: load snapshot, provision scopes, then unplug
python run.py fetch-basemap        # Protomaps extract into web/console/public/tiles/
python run.py citizen-dev          # :5174 (console is :5173)
python run.py citizen-apk          # sideload APK (Docker; not Play Store)
python -m pytest tests/ -q
python scripts/check_no_hardcoding.py
python scripts/check_pwa_config.py
python scripts/capture_backoff_log.py --date YYYY-MM-DD   # Part 19 backoff evidence
python scripts/gen_pwa_icons.py                           # regenerate citizen PWA icons
```

**Demo-day order.** The worker is the one piece that is not hosted, so it is the
one piece you have to remember. **Do not Send alert 6 again.**

```powershell
$env:PYTHONIOENCODING = "utf-8"
# ml-load needs a .venv-ml and ~3.5 GB of weights that are NOT on this
# laptop. It cannot fill a translation tonight. Keep it out of the demo path.
python run.py worker-cloud       # KEEP OPEN — sends SMS + IVR + FCM
```

On the citizen phone (or localhost Chrome): sign in, tap **Enable alerts**,
then send a **new** warning. Push permission after the fact does not rewrite
an already-queued delivery. Trial IVR: any key, then 1 or 2.

Officers: `officer.a@setu.example` / `officer.b@setu.example` (Vythiri).
Help needed = trapped person → assign team. Send a runner = village unreached
→ “I told people in person.”

Everything else — API, PWA, ops console, database, queue — is already running
in the cloud. Render `CORS_ALLOWED_ORIGINS` must include both Vercel origins
(`https://setucitizen.vercel.app,https://setuconsole.vercel.app`) with **no
trailing slash**, plus `http://localhost:5173` / `:5174` for local Vite.

---

## How to keep this file honest

- Move a task between sections the moment its status changes — don't batch updates.
- When something in 🔴 Blocked gets unblocked, move it to 🟡 and add a note in
  `docs/IMPLEMENTATION.md` if the unblocking taught us anything.
- If a task turns out to need something the design spec didn't anticipate, say so
  here in one line — don't silently absorb it.
