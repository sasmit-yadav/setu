# SETU — 10-minute SIH pitch (23 Aug)

Deck: `docs/SETU_SIH2026_Idea_FINAL.pdf` (6 slides). Speak this file; do not
read `IMPLEMENTATION.md` on stage. When a judge asks “how,” answer from
**§B** of this file. When they ask “is that live,” answer from **§C**.

**Team:** Fourth Principle · JIIT
Sasmit Yadav (lead), Meghna Tomar, Yug Thakral, Shreya Goel, Gautam Garg,
Harsh Vardhan Singh

**Problem statement:** Last-Mile Delivery Verification and Audit Platform
for Disaster Early Warnings · MHA / NDMA · Disaster Management · Software

**Live URLs (say them once, do not type them from memory):**

| App | URL |
|---|---|
| Officer console | https://setuconsole.vercel.app |
| Citizen PWA | https://setucitizen.vercel.app |
| API health | https://setu-api-6ujx.onrender.com/health |

**The one sentence, if they only remember one:**
India already tells a billion people a disaster is coming. Nothing tells
you whether one of them heard it. That is the layer we built.

---

## How to use ten minutes

| Clock | Slide | What you are doing |
|---|---|---|
| 0:00–1:10 | 1 | Open on Wayanad. Name the gap. Name SETU. |
| 1:10–2:40 | 2 | Walk the nine verbs and the architecture. Point. Do not list every box. |
| 2:40–7:10 | console + phones | **The product.** Compose → Two-Eyes → Send → ladder → Help needed. |
| 7:10–8:20 | 3 | Stack + honesty about what is live vs what is specified. |
| 8:20–9:20 | 4 | ₹0, TRAI, bootstrap model, worker on this laptop. |
| 9:20–10:00 | 5 | Impact + close. Slide 6 is Q&A, not spoken. |

If they cut you at six minutes: finish the demo, then the close in §A.6.
If they skip the demo: still do Two-Eyes + one ladder screenshot + Help vs
runner. Those three are the product.

**Do not Send alert 6.** Compose a **new** Extreme on Muttil North (ADM5
**8157**) only. Alert 6 is already live Extreme; a second Send burns Twilio
minutes and another IVR blast.

---

## A. Spoken script (read almost verbatim)

Pace: ~140 words/minute. Pause after the death count and after “that is
the layer we built.” Point at the slide; do not turn your back on the room.

### A.1 Slide 1 — Title (0:00–1:10)

On 29 July 2024 an NGO warned a district office sixteen hours before the
Wayanad landslide. Two hundred and thirty-one people died. The collector’s
office said it never received the warning. Someone had to file an RTI to
ask what happened. There is still no answer — because nobody was recording.

India predicts disasters reasonably well. It fails in the last fifty
kilometres: did the warning leave the office, reach a phone, get understood
in that village’s language, and get a reply. Cyclone Ockhi and Irshalwadi
are the same failure with different weather.

SACHET can tell a billion people a disaster is coming. It cannot tell you
whether one of them heard it, who authorised it, or what happened to the
person who could not get out.

SETU is that missing layer. We do not replace IMD or SACHET. We sit
underneath them. We prove four claims — authorised, delivered, understood,
acted on — and where we cannot prove a claim, the screen strikes it through
and prints the reason. We never invent a percentage to look busy.

We specified forty-two features. We can target every Indian sub-district.
We cache twenty-two scheduled languages. Delivery evidence has six tiers.
And we start with **zero government integrations** — USGS, GDACS and
Open-Meteo are already public.

### A.2 Slide 2 — Proposed solution (1:10–2:40)

Point at the nine verbs on the left, then the diagram on the right. One
breath each.

**Ingest.** USGS earthquakes, GDACS cyclones and floods, and our own
thunderstorm nowcast from Open-Meteo. They land as **drafts**. They do not
blast phones. An officer still decides.

**Target.** PostGIS against eight thousand three hundred admin units —
nationwide sub-districts, plus village geometry in Kerala and Maharashtra.
Compose shows enrolled people, estimated population, and buildings before
you send.

**Authorise.** Six automated checks. A human-written Extreme needs two
distinct officers. A USGS earthquake does not wait — the feed is the
authoriser, and we write that provenance on the row.

**Deliver.** On Extreme, every numbered phone gets push and SMS at once and
a voice call ten seconds later — all three go regardless; the gap only stops
the handset ringing while the message is still landing. Severe uses the same
three channels but waits far longer between them, so we do not spend Twilio on
a Moderate that a push already covered. The siren is **not** part of Send: it
wakes a whole village whether or not anyone there owns a phone, so an officer
presses it against a named warning and the ledger carries their name.

**Predict.** A reach-failure score from terrain, towers and rainfall. It is
badged **bootstrap**. We say n equals two out loud — Wayanad and
Irshalwadi. No Indian system has acknowledgement history to train on. We
did not fake a dataset.

**Assure.** Six evidence tiers beside the delivery state machine. WhatsApp
taught India this ladder: one tick, two ticks, blue ticks. Ours is
admissible. SMS has no read receipt, so **Opened is struck through** with
that reason — we do not guess.

**Respond.** Safe or Help, from the app or from the keypad on a feature
phone. Help opens a case. Safe does not.

**Relay.** If nothing real reached the village, the desk gets **Send a
runner** — panchayat, police, ASHA. That is not the same queue as a person
who asked for rescue.

**Prove.** Every state change writes an audit row in the same transaction.
The ledger is append-only. `UPDATE` on it raises. An RTI can reconstruct
the day.

Point at the diagram: sources at the top, PostGIS in the middle, Redis
fan-out, then FCM, Twilio, siren, human, peer. Citizen PWA and ops console
at the bottom. Footer line: every figure on that desk resolves to a row
with a source, a fetch time and a checksum — or it does not ship.

### A.3 Live product (2:40–7:10) — this is the pitch

Hands on the console. Citizen phone unmuted, Chrome PWA installed, alerts
enabled **before** Send. Worker terminal visible is a feature, not a mess
— say it: “the free host has no background worker; this laptop is the
sender; if it sleeps, nothing sends.”

**Beat 1 — the two products (20 s).**
Dark desk for a seated officer. Light citizen app for a frightened person
in the dark — a dark screen in a flood reads as a dead phone. Eighteen
pixel type, one thumb, one question. We designed them twice on purpose.

**Beat 2 — compose (50 s).**
Write warning → Muttil North only → Extreme. Show the preview: enrolled
count, population, buildings. Validate. If expiry or Malayalam is missing,
the **quality gate names the rule next to the disabled Send** — not a
toast. The six rules are: geometry exists, expiry set, target count
plausible, escalation policy exists, translation exists for this state’s
severity, area not absurd. Area over the cap is a **warn**, not a silent
fail.

**Beat 3 — Two-Eyes (40 s).**
Officer A approves. Show the **409: have 1, need 2**. Same officer cannot
self-quorum. Officer B on the second login. Say: “a human-composed Extreme
needs two humans. An earthquake from USGS records `authoritative_source`
and goes. We measure our own delay: approval wait p50 and p95.”

**Beat 4 — Send (70 s).**
Send. Four verified trial SIMs get SMS and IVR together. Phones with a
live FCM token also get a push. Open one recipient’s assurance ladder:

- Attempted — we tried.
- Provider accepted — Twilio / Firebase said yes. We have real
  `provider_accepted` rows from yesterday’s Extreme.
- Device delivered — carrier callback on SMS. For FCM we claim this only
  if the phone’s service worker called home.
- Opened — **struck through on SMS**. No Indian carrier gives a sender a
  read receipt. The reason is in the database, rendered verbatim.
- Acknowledged — they opened the card or answered the call.
- Citizen response — they said Safe or Help. Receipts are not replies.

On Extreme we do not skip the call because they opened the app. The app
can be in a pocket.

**Beat 5 — the villager (50 s).**
Citizen signs in with OTP on their own number — that SIM is that person,
not a shared village inbox. Headline reads aloud on the phone’s own
speech engine, same signed text, **not an LLM**. Nearest safe zone is a
real OSM row: Community Hall, Muttil, about 820 metres, with a
road-conditions disclosure. Tap **Help → Trapped**.

**Beat 6 — Help needed ≠ Send a runner (40 s).**
Help needed is `assistance_case`: this person asked for rescue. Five
named factors, score 0–100, Give to team **on the row**. Send a runner is
`human_relay`: this **village** never got the warning. Ack is not a
reply. Opened-or-answered is not Help. If they mix those three, the 2024
RTI happens again inside our own console.

**Beat 7 — only if they ask, 20 s each.**

- *Offline / Gate 3:* Android Chrome → Add to Home Screen → airplane
  mode → reopen. Banner: “No signal. This is the copy already on this
  phone.” Help while offline says it was **not** sent. Do not claim a
  pending queue. Do not use the sideload APK for this beat — WebView has
  no Push API.
- *Nearby / B10:* Share a signed `?peer=` URL. Phone B shows **PEER**
  only after Ed25519 verifies. One hop, not a mesh, not radio. A web page
  cannot advertise Bluetooth.
- *Official feeds empty:* We checked. GDACS current India is zero. USGS
  has no quake on Wayanad. Empty is honest. We still send on Muttil
  because that is the enrolled village we can prove. Feeds never
  auto-blast a human-written Extreme.

### A.4 Slide 3 — Technical approach (7:10–8:20)

We did not invent a new primitive. Polygon intersection, a work queue, a
state machine, a hash chain.

**Frontend.** Two Vite + React + TypeScript apps. Citizen is a PWA with
Workbox: installable, offline cache, our own service worker for FCM.
Console is MapLibre plus a self-hosted Protomaps extract so the map is a
file, not a CDN that goes blank when the network dies. Command palette
Ctrl+K, because forty-two features do not fit a nav bar.

**Backend.** Python, FastAPI, Pydantic, asyncpg. Postgres + PostGIS on
Neon. Redis Streams on Upstash. Alembic migrations to 0016. The API never
imports torch — CI fails the build if it does — because two transformer
models will OOM a 512 MB free API box. Translation lives in a separate
process. **IndicTrans2 runs here now** — the dist-200M card in its own
container, and `model_registry` row 2 is the model registering itself after a
real response. Compose a warning in any wording and Malayalam, Hindi and
Marathi are translated and cached before you can reach the Send button. Rows
translated by the model carry its `model_id`; alert 6's older Malayalam was
entered by hand and carries NULL, and the difference is visible in the data.
Where a language has no cached row the app falls back to the source text and
prints the reason on screen.

**Channels.** Firebase FCM, Twilio SMS and IVR, optional email, a siren fired
by webhook to a real controller (a laptop stands in for the panchayat's) and
sounded by an officer rather than by the dispatch, human relay, signed peer
payload. Anything that does fall back to the simulated carrier is flagged
`simulated=true` and badged **SIM**. Ed25519 signed on the server, verified on the device before
anything renders. An unverified payload is discarded silently — a
“suspicious alert” banner is its own panic vector.

**Delivery state machine.** Eight states as data: pending, queued, sent,
delivered, acknowledged, failed, expired, escalated. Illegal transitions
cannot be written. Branch coverage on that package is 95.87 percent, gated
in CI. Assurance events sit **beside** the state machine, not inside it,
so a webhook cannot rewrite history.

**ML, said carefully.** MiniLM embeddings only **veto** a duplicate when
the embed endpoint actually returns vectors; shipping dedup is PostGIS
spatial-temporal with measured precision and recall on 200 labelled pairs.
IndicTrans2 dist-200M translates for twenty-two languages, cached per
sentence so IVR and the PWA say the same words and a repeated warning costs
the model nothing. It is a separate process from the API by design — the API
cannot import torch and CI fails the build if it can. Rows it wrote carry its
`model_id`; rows a human typed carry NULL. We do not have to be asked which
is which. Thunderstorm nowcast from CAPE and
lifted index — **cannot self-authorise**. Copilot RAG is phase two; we are
not demoing it.

### A.5 Slide 4 — Feasibility (8:20–9:20)

**Technical.** No new research. Every dependency fetched twice. GADM was
rejected on licence; we use geoBoundaries ODbL.

**Economic.** This pilot is **₹0**. Firebase Spark, Neon free, Upstash
free, Vercel, Render free web, Twilio **trial credit not purchased**. We
do not claim free scales to a billion people. National volume is a
paid-tier migration on the same architecture, not a rewrite.

**Operational.** A new source or channel is one INSERT into the adapter
table. The worker is this laptop because Render free has no background
workers. That is a hosting fact, not a missing feature.

**Legal.** Consent is a database constraint. A relay volunteer gets a
**count and an area, never a list of who asked for help**.

**The risks we already named on this slide, and what is true today:**

- Nationwide SMS needs TRAI DLT and a registered entity. We send real SMS
  to four verified trial numbers. Everyone else hits the identical engine
  against a simulated carrier, flagged and badged. We never pretend.
- IMD’s public API returned 401 on every documented endpoint. SACHET has
  no public alert-discovery feed we can poll. Both are optional upgrades.
  USGS, GDACS and Open-Meteo already ingest.
- Peer relay as Bluetooth GATT peripheral is impossible in a browser. The
  live fallback is the signed link.
- Free-tier Redis: idle retry polling was going to exhaust the daily
  command budget. We measured it, raised the block timeout, and landed at
  4.08× headroom, not 5×. We say the shortfall. Stop the worker between
  rehearsals.

### A.6 Slide 5 — Impact and close (9:20–10:00)

Today: a blanket broadcast, no per-person record, no authorisation trail,
no way for a trapped person to answer, and after the event an RTI with
nowhere to look.

With SETU: attempted → accepted → delivered → opened → acknowledged →
answered. Hash-chained. The authorisation is on the same record as the
help request. The answer exists before the question is asked.

Who it changes:

- The district officer sees which village is silent, and which person
  inside it asked for help, ranked, with the factors named.
- The citizen gets the warning in their language, still on the phone if
  the tower dies after the cache, and can tap or press 2.
- An auditor queries a database instead of a collector’s memory.
- NDMA gets reach by district and channel, not a dispatch count.
- A runner gets a count and an area. Not a list of names.

Pilot is two districts on live global feeds, zero ministry MoU. State is
their CAP feed as a row. National is SACHET as the pipe and SETU as the
proof.

Wayanad, Ockhi, Irshalwadi: more than seven hundred and forty dead, more
than three hundred and sixty missing, and warning arrival always
disputed.

**SETU does not promise a better forecast. It promises that the next
dispute has an answer.**

The duty exists. The feeds exist. The handsets exist. What was missing
is the record — and the answer back.

Stop. Hands off the keyboard. Take questions.

---

## B. Whole implementation — what you actually built

Use this in Q&A. Do not recite it. Numbers are from the live system as of
22 Aug 2026 (`IMPLEMENTATION.md`). If this file and the spec disagree, the
running system wins.

### B.1 What SETU is

A disaster-alert **delivery, acknowledgement, response and audit**
platform. Central discipline: a channel or a model is never allowed to
claim a stronger evidence tier than it can produce. Where evidence does
not exist (SMS read receipts, siren confirmation, earthquake lead time),
the reason lives in a database column and is rendered verbatim.

### B.2 Two products, opposite rules

| | Officer console | Citizen PWA |
|---|---|---|
| Who | Seated, trained, at a desk | Frightened, standing, maybe dark |
| Theme | Dark-first, angular panels | Light-first (dark = dead phone) |
| Type | 14–16px, JetBrains Mono on numbers | 18px minimum, one thumb |
| Network | Assumed present | Assumed absent |
| Session | `sessionStorage` (shared DEOC desk) | `localStorage` (personal phone) |
| Host | setuconsole.vercel.app | setucitizen.vercel.app |

Only three ideas appear in both — alert card, assurance indicator,
language switcher — and each is designed twice. Console CSS must not be
imported by the citizen app.

**Console screens that matter on stage:** Map → Write warning → Help
needed → Send a runner → This emergency → Overview. Ctrl+K still works;
chords are not painted on the nav. Live Ops does **not** fill official
polygons on the map (that looked like a pre-marked disaster). “From
official sites” is the draft inbox. “Opened or answered” is the ack KPI,
not citizen replies. Replies have their own safe / need-help counts.

**Citizen:** OTP to the SIM, or email `citizen@setu.example` for the
village PWA row (recipient 5, not phone 1). Village inbox — no typed
delivery ID. Auto-read + tap-to-read via OS `speechSynthesis`. Airplane-
mode banner. Honest Help errors.

**Sideload APK:** `python run.py citizen-apk` → WebView of the hosted
PWA. Home-screen icon and login that survive app close. **Not** Enable
alerts, **not** Gate 3, **not** Play Store.

### B.3 Data plane

- **Postgres + PostGIS** on Neon (Singapore). Schema through migration
  **0016**. 8,302 `admin_unit` rows: ADM3 nationwide + ADM5 Kerala and
  Maharashtra. 281 OSM safe zones. 5 Muttil North recipients. Slide “6,836
  sub-districts” is the ADM3 count from geoBoundaries; the running database
  is 8,302 because villages in two states are loaded on top.
- **Almost every `parent_id` is NULL** (ADM3 and ADM5 are not a tree in
  this load). Officer scope is geographic `ST_Intersects`, not a parent
  walk. Muttil North 8157 was patched under Vythiri 3081 so the first list
  query could see Help cases; the code fix is the same intersection
  predicate.
- **Redis Streams** on Upstash. Fan-out is batched. Worker is
  `python run.py worker-cloud` against `.env.cloud`. Render’s worker
  service is **suspended** — free tier has no background workers.
- **Geometry honesty:** village shapefile nationwide is ~1.01 GB vs 0.5 GB
  free DB, so villages only in the two case-study states. Hosting cost,
  not a technical barrier.
- **OpenCelliD** coverage is partial; reach-risk says so.
- **Copernicus GLO-30:** four tiles for Wayanad + Palghar present (`COG_10`
  not the spec’s `COG_30`). No SRTM fallback needed there.

### B.4 Ingest

| Source | What | Auth | What SETU does |
|---|---|---|---|
| USGS FDSN | Earthquakes | none | Draft; `is_authoritative` can auto-approve |
| GDACS | Cyclone/flood/fire/drought | none | Draft; GDACS `/MAP` 400s without `eventtype` — we use `/SEARCH` |
| Open-Meteo | CAPE, LI, CIN, precip | none | Thunderstorm nowcast every 15 min; **cannot** self-authorise |
| IMD public API | — | 401 on documented endpoints | Optional upgrade, not load-bearing |
| SACHET | National CAP pipe | no public discovery feed | Optional upgrade; we are the layer underneath |

22 Aug afternoon check: USGS 24h India-box = M4.1 Afghanistan; GDACS
current India = 0; Wayanad box = 0. **Do not wait for a quake.**

Dedup: spatial/temporal cluster, one live version per incident. MiniLM
only vetoes when `/embed` returns real vectors. Held-out 200 pairs;
P/R on Methodology screen.

### B.5 Governance

**Quality gate (all 6 live):** `geometry_non_empty`, `expiry_set`,
`target_count_plausible`, `escalation_policy_exists`, `translation_exists`,
`target_area_plausible` (warn). Kerala Extreme requires Malayalam;
Palghar uses Marathi — not a global `ml` floor.

**Two-Eyes:** quorum by severity. Same officer twice = one approval row.
Authoritative feed = `provenance='authoritative_source'`, zero human
steps.

**Versioning:** v2 supersedes v1; in-flight deliveries expire with
`reason='superseded_by_version'`. One active alert per incident
(unique index).

**Fatigue:** relabels a repeat (`URGENT UPDATE — ` from config).
**Structurally cannot suppress Extreme.**

### B.6 Delivery

**State machine** (8 states, `FOR UPDATE`): pending → queued → sent →
delivered → acknowledged / failed / expired / escalated.

**Assurance ladder** (separate `delivery_event` log, 6 tiers):
`delivery_attempted` → `provider_accepted` → `device_delivered` →
`notification_opened` → `acknowledged` → `citizen_response`. Level is
derived by SQL `assurance_level()`, never a writable column.

**Channels:** fcm, sms, ivr, email, siren, sim, human_relay,
community_relay. Capability is a table: `channel_capability_tier`.
Unsupported rungs **must** have `not_applicable_reason`. CI
`check_channel_capability.py` fails if adapter flags and the table
disagree.

**Extreme vs Severe (22 Aug product rule):**

- Extreme: SMS + IVR + FCM **simultaneous** for every numbered phone.
  Push is extra, not a substitute.
- Severe: same three channels, but `hold_staggered_channels` parks SMS
  then IVR on the retry zset (`wait_before_next_s` 180 s then 120 s).

**Retry / B3:** was dead code until 21 Aug. Now policy-driven growth +
jitter (60 → 90 → 135 s on Extreme SMS, ±2.5 s). Captured log is
`IMPLEMENTATION.md` §12.1. `on_channels_exhausted` only after the
**chain** dies — not after one `ChannelUnavailable`. Simulated siren used
to count as delivered and skip the human; new Extreme opens `human_relay`
when no **real** fcm/sms/ivr/email was sent.

**STOP:** sets `opted_out_at`; that recipient is never enqueued again.

### B.7 Response and assistance

`POST /response` types from config: safe, trapped, medical,
unable_to_evacuate, other. SAFE does not open a case. Help types do.
Priority: five named factors + weights + `weight_version`. Location
requires `location_consent=true` (DB CHECK).

**Help needed** = cases. **Send a runner** = pending human_relay tasks.
Relay confirm: HTTP “I told them in person” (live). IVR DTMF runner
confirm exists in code and has **never** been called on stage. Citizen
IVR 1 = SAFE **has** been called (alert 6 delivery 8).

Relay node token may hit `/assistance/summary` (count + area) and gets
**403** on `/assistance` (no list of who asked).

### B.8 Crypto, PWA, peer

Server signs every alert Ed25519 (`ALERT_SIGNING_SEED_B64`). Public key
is baked into the PWA (`VITE_ALERT_SIGNING_PUBKEY_B64`). Rotating the
seed is a **release**. Phone hash pepper and pgcrypto key are
**migrations**.

Peer: signed `?peer=` URL, verified before render. GATT client code still
exists; peripheral role does not exist in browsers. Say the URL path.

Citizen SW caches the open alert (`setu-deliveries-v1`). FCM path is
**data-only** so the SW runs (a `notification` block is eaten by the tray
and never returns the receipt nonce).

### B.9 ML isolation

`services/ml` on `:8001`. `SETU_LOAD_ML_MODELS=1` loads weights.
`check_no_torch.py` keeps torch out of the API. HF Space **not deployed**.
Demo translations: `python run.py ml-load` then `translate-cloud` before
Validate on a new Kerala Extreme. PWA/IVR read `alert_translation`. If the
fallback notice shows, that is the honest miss.

### B.10 Enrollment

Phone HMAC with pepper. CSV import idempotent, mandatory dry-run first.
16 older CSV rows have `phone_enc IS NULL` (key was missing); those
numbers are unrecoverable. Demo path is the four Twilio-verified SIMs
plus the PWA row.

Citizen device: `POST /citizen/device` binds FCM to **that login’s**
recipient.

### B.11 Tests, guards, freeze

21 Aug: **267 tests passed**, 2 skipped, `services/delivery` **95.87%**,
six guard scripts green, `ruff check services/` clean. 196 `app_config`
rows, 8 channels, 32 capability tiers, 23 audit event types, 140 RBAC
tests. Part 19 walk: **41 verified / 11 partial / 6 not done / 1 waived**
— `IMPLEMENTATION.md` §11.

Guards: no hardcoding, no torch in API, env-example drift, channel
capability, seed counts, freeze-guard.yml (epoch 21 Aug 21:00 IST).

### B.12 What is not done (say it; do not hide)

| Gap | Honest line |
|---|---|
| 21-step recorded take | Needs six people and a camera. Not done. |
| Two-Eyes 10× rehearsal | Show 409 once. Do not promise ten consecutive. |
| Gate 3 cable-pull | Airplane mode on Chrome PWA. Building stays plugged in. |
| FCM `service_worker` receipt on presenting phone | Enable alerts **before** Send; claim device-delivered only if that row exists. |
| HF Space | Laptop model + cache. |
| B10 radio | Signed URL. |
| B9 runner DTMF | HTTP confirm on stage. |
| Nationwide SMS | Four trial SIMs. SIM badge otherwise. |
| Slack/Discord webhook | Empty. Nothing pages you if the worker dies except your eyes. |
| Email channel | Needs Brevo/Resend. |
| Sixth Twilio number | Trial cap is 5. Do not add more. |

---

## C. Live Extreme already proven (do not re-send)

**Alert 6** — Extreme, Muttil North 8157, Malayalam + English, Two-Eyes,
headline as stored. Its Malayalam row is hand-entered with no `model_id`; the
delivery evidence below is the real part. Recipients:

| id | Who | What actually left |
|---|---|---|
| 1 | +91 79882 43529 | real SMS + IVR + FCM |
| 2 | +91 97111 17266 | real SMS + IVR (no push token) |
| 3 | +91 87979 75654 | real SMS + IVR + FCM |
| 4 | +91 93192 77596 | real SMS + IVR + FCM |
| 5 | citizen PWA email | FCM `device_unregistered`; no phone; simulated siren |

Trial IVR: press **any key** for Twilio’s trial lady, **then** 1 (safe) /
2 (help).

Officers: `vythiri.a@setu.example` / `vythiri.b@setu.example`, scope
Vythiri ADM3 **3081**. Password is `SETU_DEMO_PASSWORD` in `.env` — never
read it aloud, never put it on a slide.

Recipient 5 needs **Enable alerts** again before the next Send or FCM
fails honest.

---

## D. Questions they will ask

| They say | You say |
|---|---|
| Is this a real disaster? | No. Wayanad is quiet. We checked USGS and GDACS. We demo the last mile on enrolled phones. |
| A separate portal per district? | No. One console, one ledger. Scope is a property of the account, not the URL — a Wayanad officer and a Palghar officer sign into the same desk and see different taluks, refused server-side on every request. Seven hundred portals would mean seven hundred audit trails, and one queryable ledger is the point. |
| Why not SACHET / IMD? | They are the national pipe and the forecast. We are proof after the pipe. IMD’s public API 401s; SACHET has no pollable feed. Both are upgrade rows, not blockers. |
| 88% delivered? | We do not show that. We show struck rungs. SMS has no read receipt. |
| Is this AI / LLM voice? | OS text-to-speech of the signed headline, never an LLM. Translation is IndicTrans2 dist-200M running in its own container, registered in `model_registry`, and every row it wrote names it. |
| Play Store app? | Sideload WebView for the icon. Push is Chrome → Add to Home Screen. |
| Mesh / Bluetooth? | One signed hop. A browser cannot advertise GATT. |
| Why four phones not India? | TRAI DLT. Real SMS to verified trial numbers. Simulated carrier otherwise, badged SIM. |
| Why is the worker a laptop? | Render free has no background workers. The queue is real Upstash. Sleep = silent send. |
| Can a fake alert be injected? | Unverified Ed25519 payload never renders. |
| Two-Eyes delays life-safety? | Only human-composed Extreme. USGS does not wait. We publish approval wait times. |
| Reach-risk accurate? | Bootstrap, n=2, badge on screen, methodology endpoint. |
| Offline? | Cached alert on installed Chrome PWA. Not the APK. Help while offline is not queued as if it sent. |
| Cost at national scale? | Pilot ₹0. Paid-tier migration, same architecture. SMS/IVR only when reach is predicted to fail. |
| RTI / audit? | Append-only ledger, trigger rejects UPDATE/DELETE, timeline API, PDF export path. |
| Privacy for runners? | Count and area. 403 if a relay token asks for the name list. |
| Why Muttil? | Case-study village, enrolled SIMs, OSM hall 820 m, Malayalam required. |
| Auto-send the feed? | Drafts until an officer (or an authoritative provenance) dispatches. We will not invent a landslide to look busy. |

---

## E. Never say

- Mesh network / BLE radio between two PWAs
- Live Hugging Face Space
- We unplugged the building
- Nationwide SMS
- Send alert 6 again
- Help needed is the same as Send a runner
- Opened-or-answered is a reply
- 88% delivered
- The APK receives push
- The pending banner means it will send later
- Copilot / RAG is in this build
- Tailwind (the console is custom tokens + CSS)
- IMD is integrated

---

## F. Pre-stage checklist (T–30 min)

1. `curl https://setu-api-6ujx.onrender.com/health` — if cold, wait ~50 s and
   retry. Keepalive should have it warm.
2. `python run.py worker-cloud` with `PYTHONIOENCODING=utf-8`. Laptop
   awake, terminal in sight. Render worker stays suspended.
3. Console Root Directory is `web/console`. Hard-refresh. Login Officer A
   and B in two browser profiles.
4. Presenting phone: **Android Chrome → Add to Home Screen**, sign in,
   **Enable alerts**, unmute. Confirm a `push_token` on that recipient.
5. Do not Send alert 6. Compose **new** Extreme, Muttil North only.
6. Start the translator before the console: `docker start setu-ml`, then
   check `curl localhost:8001/health` shows `toolkit: true`. With it up, any
   headline you compose is translated before Validate. With it down, only
   already-cached wording passes the Kerala gate.
7. Twilio trial: any-key then 1/2. Four SIMs in the room, not in a bag.
8. One spare Chrome tab for the signed peer URL if they ask nearby.
9. `/api/v1/methodology` bookmarked if they ask thresholds.
10. If the worker dies mid-demo, say so and restart. Do not pretend the
    queue is draining.

---

## G. Slide 6 — references (Q&A only)

Do not read the fourteen sources. If they ask “where did you get X”:

1. NDMA SACHET CAP / Integration Guide — we sit underneath, not instead.
2. IMD public API — 401; upgrade track.
3. USGS FDSN — live ingest, zero auth.
4. GDACS JSON — live ingest, zero auth.
5. Open-Meteo — nowcast inputs, keyless.
6. OASIS CAP 1.2 + DM Act 2005 — interchange + statutory duty to warn.
7. geoBoundaries gbOpen ADM3/ADM5 ODbL — GADM rejected.
8. OSM Overpass — safe zones.
9. IndicTrans2 dist-200M MIT — 22 languages, CPU, not the 1B GPU model.
10. TRAI DLT / Twilio India — why nationwide SMS is not ours yet.
11. Copernicus GLO-30, WorldPop, Open Buildings, OpenCelliD — reach-risk
    features.
12. Wayanad 2024, Ockhi 2017, Irshalwadi 2023 — the failure mode.
13. Protomaps PMTiles — offline basemap file.
14. Ed25519 RFC 8032 — signed alerts, signed peer URL.

Every source was fetched. Unverified sources are marked. Missing signals
publish a reason, never a placeholder number.

---

## H. If time collapses

**90 seconds:** Wayanad RTI with no record → last fifty kilometres → we
prove authorised / delivered / understood / acted on → struck rungs when
we cannot → two officers, four real phones, Help is not a runner.

**3 minutes:** 90-second open + Two-Eyes 409 + one ladder with Opened
struck through + Help needed row.

**Then sit down.** The close line still fits: we do not promise a better
forecast. We promise the next dispute has an answer.
