# SETU — Current Tasks

Status-based, not day-based. Update this file whenever a task's status
changes — this is the file to open to answer "what do I do next."

For "how does the system work / why is it built this way," see
`docs/IMPLEMENTATION.md`, not this file.

**Legend:** 🔴 Blocked (needs an external account/credential/decision) ·
🟡 Ready to build (nothing blocking) · 🟢 Done · ⚪ Not started, not urgent

---

## 🔴 Blocked — need an external account, credential, or decision

| Task | Blocked on | Who |
|---|---|---|
| Point the app at a cloud database | Neon account + pooled/direct URLs | — |
| Real push notifications | Firebase project + service-account JSON + **VAPID key pair** (web push certs — easy to miss) | — |
| Real SMS / IVR / human-relay calls | Twilio account + verified phone numbers (need 6–8: 2–3 for demo beats, 6 for relay-node seeds) | — |
| Relay-node seed data | The above, plus real phone numbers to replace `data/seeds/05_relay_nodes.sql`'s placeholder ciphertext | — |
| Tower-density features (D8f) | OpenCelliD token (fires the request, then wait — has a queue) | — |
| Email escalation channel | Brevo or Resend API key | — |
| Monitoring alerts | A Discord/Slack incoming webhook URL | — |
| **Decision:** is B10 (Community Relay Mode) buildable at all? | 20-minute spike, two Android phones + Chrome DevTools — confirm whether Web Bluetooth exposes any GATT peripheral/server role. See `docs/IMPLEMENTATION.md` §6.1 | — |
| **Decision:** where does the ML service run? | Needs a host that isolates `torch`/`transformers` from the API process | — |

## 🟡 Ready to build — nothing external blocking these

- [ ] `services/governance/quality_gate.py` — F1: pre-dispatch rules reading
      thresholds from `app_config` (`quality_gate.*` keys already seeded).
      Start with `min_target_count`, `require_expiry`, `max_target_area_km2`.
- [ ] `services/governance/approvals.py` — F3: `alert_approval` insert logic,
      quorum check reading `approval.required.<severity>`, the
      `authoritative_source` auto-approve path for `is_authoritative` sources.
- [ ] `services/delivery/state_machine.py` — the 8-state transition table +
      `transition()` with `FOR UPDATE` locking. This is the module that will
      eventually carry a 95%-branch-coverage floor — write it carefully and
      test it before anything else builds on top.
- [ ] `services/delivery/assurance.py` — `assurance.record()`: idempotent
      insert into `delivery_event` (`ON CONFLICT DO NOTHING` on
      `(delivery_id, event_type)`).
- [ ] `services/delivery/channels/simulated.py` — `SimulatedCarrierAdapter`.
      No external dependency, and it's what every other channel gets tested
      against before real credentials exist.
- [ ] `services/crypto/alert_signing.py` — Ed25519 sign/verify using
      `ALERT_SIGNING_SEED_B64`. Useful regardless of the B10 decision (§6.1) —
      also verifies the FCM push payload.
- [ ] `services/ingestion/adapters/usgs.py` + `gdacs.py` — both are zero-auth,
      confirmed-live feeds. Can be built and tested against real endpoints
      right now with no account needed.
- [ ] `services/response/priority.py` — D11f's weighted-sum formula, reading
      `assistance.weight.*` (already seeded).
- [ ] `scripts/check_channel_capability.py` — CI gate asserting adapter
      classes' declared capability flags match `channel_capability_tier`.
      Write this *before* or *alongside* the first real adapter, not after.
- [ ] `scripts/check_no_hardcoding.py` — Rule 1 AST-walker over
      `services/{delivery,targeting,governance,response}`.
- [ ] Basic `tests/property/` — at minimum, the "no channel reports an
      unsupported tier" and "single officer cannot satisfy quorum" property
      tests, since the schema constraints they check already exist.
- [ ] Load ADM3 admin-unit geometry (§1.6.2 in the design spec) — this is
      needed before `05_relay_nodes.sql` can seed anything, and before D7f/D8f
      views return real rows. No account needed, just the geoBoundaries
      download + `ogr2ogr` load.

## 🟢 Done

- [x] Repo initialized, `.gitignore`, venv on Python 3.12.1
- [x] `requirements.txt` pinned (169 packages, PyNaCl included, zero
      torch/transformers)
- [x] `infra/docker-compose.yml` — Postgres+PostGIS (port 5433), Redis,
      MailHog, all healthy
- [x] Migrations `0001`–`0012` written and applied; round-tripped
      (`upgrade head → downgrade 0006 → upgrade head`) clean, twice — once
      empty, once with seed data loaded
- [x] Seed files `01`–`05` written and applied (`05` correctly no-ops
      pending geometry load)
- [x] `scripts/verify_seeds.py`, `doctor.py`, `gen_secrets.py`,
      `wait_for_db.py`, `guard_local_only.py`, `run.py` written and working
- [x] Real local secrets generated (`PHONE_HASH_PEPPER`,
      `ALERT_SIGNING_SEED_B64` + public key, JWT/HMAC secrets) — in `.env`,
      not committed
- [x] `docs/IMPLEMENTATION.md` and this file created

## ⚪ Not started, lower priority for now

- [ ] Frontend — both `web/console` and `web/citizen` are empty directories
- [ ] `services/ml` — no code, no hosting decision (see Blocked)
- [ ] CI workflows (`.github/workflows/`) — none written yet
- [ ] Snapshot/demo-fixture tooling
- [ ] Design tokens (`packages/tokens`)

---

## How to keep this file honest

- Move a task between sections the moment its status changes — don't batch
  updates.
- When something in 🔴 Blocked gets unblocked, move it to 🟡 and add a note
  in `docs/IMPLEMENTATION.md` if the unblocking taught us anything (a gotcha,
  a deviation from the design spec, a wrong assumption).
- If a task turns out to need something the design spec didn't anticipate,
  say so here in one line — don't silently absorb it.
