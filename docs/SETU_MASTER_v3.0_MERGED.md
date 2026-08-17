# SETU — Engineering Specification & Build Roadmap (Merged Master Copy)
### Disaster Alert Delivery, Acknowledgement, **Response** & Audit Platform
**Version 3.0 (Merged) · 14 August 2026 · Target: SIH 2026 Internal Hackathon, 24–25 August**
**Team: 6 · Budget: ₹0 · Remaining window: 14 → 23 August (10 days) · Feature freeze: 21 Aug 21:00 IST**

> **What this document is.** v3.0 is the single master copy. It merges, in full, with nothing dropped: the v2.0 base spec (Parts 0–19), the UI North Star (Part 0.5), the v2.1 Closure Addendum (Parts 20–33), **and the Operational-Closure layer — 17 new features developed across three independent review passes** (a reachability/relay proposal, an 18-feature governance/lifecycle proposal, and the gap analysis between them). The new features are **integrated inline into the parts they belong to** — schema in Part 5, channels in Part 8, API in Part 10, screens in Part 11, day-by-day in Part 16 — not appended as a second document. Where v2.1's text was correct it is preserved verbatim; where a new feature changes it, the change is marked **[v3.0]**.

> **The one-line reason v3.0 exists.** v2.1 built a platform that could *send an alert, record delivery, and prove it*. It could not answer: was this alert *authorized*? is it the *latest version*? does "delivered" mean a human was *informed*? what happens to a citizen who replies *"I need help"*? and what happens when a village goes dark and a **person** — not a channel — has to carry the warning? Those five questions are what v3.0 closes. Nothing in it is a new alert source, a new dashboard, or a new ML model.

> **Honesty carried forward unchanged.** Every `[UNVERIFIED]` and `[RECONFIRM]` marker from v2.0/v2.1 survives into v3.0 with its stated fallback intact. v3.0 adds **no new external data dependency** — every new feature is built on data the platform already collects, a channel it already has, or a browser API that ships in the engine we already target. That is deliberate: at Day 4 of a 13-day build, a new feature that needs a new verified data source is a new risk, and we took none.

---

# PART 0.4 — UI REFERENCE & INTERACTION MODEL: WHERE THE DESIGN IS TAKEN FROM

> **Read before Part 0.5.** Part 0.5 sets the *taste bar* and Part 11 implements it in tokens. This part answers the question that sits underneath both: **what do we actually look at, and what do we deliberately refuse to copy.** Every reference below is a shipping product a teammate can open in a browser in under a minute — not a mood board.

## 0.4.1 The governing decision: this is two products, and their rules are opposites

The single most expensive mistake available to us is designing one interface and scaling it to both audiences. **The officer console and the citizen PWA invert on almost every axis**, and a pattern that is correct in one is a defect in the other.

| | **Operations console** (P1 · P2 · P5) | **Citizen PWA** (P3) |
|---|---|---|
| **Who is holding it** | A trained officer, seated, alert, at a desk | A frightened person, standing, possibly moving, possibly in the dark |
| **Literacy assumed** | Domain-fluent; reads jargon fluently | **None assumed.** May not read the alert language at all |
| **Information per screen** | Many panels — comparison *is* the job | **One question.** Nothing else on the screen |
| **Density** | High (4/8/12/16px rhythm, Part 11.1) | Low. Large targets, generous whitespace |
| **Body text** | 14–16px | **18px minimum**, and it must survive system text scaling |
| **Theme** | Dark-first | Light-first — a dark screen at night in a flood reads as "phone is dead" |
| **Input** | Keyboard-driven, mouse, command palette | **One thumb.** Assume the other hand is holding a child or a bag |
| **Motion** | Purposeful, informational (count-ups, one radar pulse) | **Near zero.** Motion during panic is noise |
| **Network** | Assumed present | **Assumed absent** |
| **Chances to get it right** | Many — they can retry, re-sort, re-read | **Possibly one** |

**The rule that follows:** any pattern we borrow gets tagged with which of the two it belongs to. A component that appears in both — there are only three: the alert card, the assurance indicator, and the language selector — is designed twice, not shared.

## 0.4.2 The officer console — what to open, what to borrow, what to leave

| Reference | Borrow | Leave behind |
|---|---|---|
| **incident.io** | The incident page as a *narrative*: a chronological timeline with actors, state changes and decisions in one column. This is the closest shipping analogue to **D10f** that exists | Their Slack-native workflow — our officer is not in Slack |
| **PagerDuty** | The triage list: severity, age, assignee, one-click acknowledge. Directly maps to **D11f** | Alert-fatigue-inducing red everywhere |
| **Linear** | The reference for **dense but calm.** Study the restraint: muted borders, one accent, generous line-height inside a tight grid, and keyboard-first everything | Its opinionated project model |
| **Cloudflare dashboard** | The best "many features, still legible" example available. Note how much is *hidden until needed* | Marketing surfaces bolted into the product |
| **Grafana / Datadog** | Live-metric layout and time-window controls | **A warning, not a model.** Both are cluttered; we have 42 features and cannot afford their density |
| **Stripe dashboard** | The payment-timeline component — a vertical event trail with per-step evidence — is almost exactly **B8's assurance ladder** in a different domain | — |
| **Flightradar24 / Windy** | Dense live geographic data that stays readable; layer toggles that do not fight the map | Consumer chrome |
| **Frostpunk · XCOM 2 · StarCraft II** *(already named in Part 0.5)* | The *feeling* of stakes, the peripheral-vision read of "where is trouble" | Everything decorative |

## 0.4.3 The 42-feature problem, and the one pattern that solves it

Twenty-eight core features cannot live in a navigation bar. The two obvious answers both fail: a wall of icons is unlearnable, and three levels of nesting means an officer hunts for a control during the ten minutes it matters.

➡️ **Decision: a command palette (`⌘K` / `Ctrl+K`), on the Linear / Superhuman / Raycast model.**

- **Navigation holds only the five screens used *during* an event** — Live Operations, Incident, Assistance Queue, Command Board, Methodology.
- **Everything else is one keystroke**: compose, validate, approve, escalate, assign, export, re-run, open a unit, jump to a village by name.
- Every command carries its keyboard shortcut in the palette, so the palette teaches the shortcuts and an officer graduates off it.
- **It is also a demo beat.** Typing `escalate` and watching the action appear reads as a professional tool in a way no menu does.

**Progressive disclosure is the companion rule** (Part 11 already implies it; this makes it explicit): a screen shows the aggregate first and the row-level detail on demand. The Command Board shows *"3 units critical"*, not three hundred rows — the rows are one click deeper.

## 0.4.4 The citizen PWA — what to open

| Reference | Borrow |
|---|---|
| **GOV.UK Design System** | **The single most important reference in this document for C6.** Their *"one thing per page"* pattern is exactly right for a frightened user: one question, large targets, plain language, no cleverness. Also the source of our icon-**and**-label rule |
| **Google Public Alerts / Crisis Response** | How a hazard is summarised in two lines above the fold, with the action first and the explanation second |
| **FEMA app · Red Cross Emergency** | Direct prior art. Twenty minutes each is worth more than an hour of moodboarding — note especially how both handle "no connection" |
| **UMANG · DigiLocker · Aarogya Setu** | **Familiarity beats novelty.** These are the government apps our citizens have already been taught. Matching their conventions costs us nothing and buys comprehension |
| **Apple Wallet boarding pass** | Part 0.5's own instinct — *"closer to a boarding pass than a war room"* — made concrete: one card, one status, glanceable at arm's length |
| **Google Maps directions card** | The safe-zone card in **C4**: destination, distance, one primary action, everything else collapsed |

## 0.4.5 The strongest single reference we have — and it is for B8

> **WhatsApp's tick system: ✓ sent · ✓✓ delivered · blue ✓✓ read.**

A billion Indians — including every judge in the room — **already understand a delivery-assurance ladder**, because WhatsApp spent a decade teaching it. This is a gift and we should take it:

- **Borrow the mental model, not the glyphs.** Tiers ascend, the top tier is visually distinct, and the meaning is learned rather than explained.
- **It makes our hardest UI problem legible for free.** Everyone has seen a message sit on one tick and known exactly what that means: *it left, and we cannot say more than that.* That is precisely what `provider_accepted` with no `device_delivered` means, and precisely what Rule 8's *"not applicable"* rung is communicating.
- **It also proves the honesty rule is not pedantry.** WhatsApp shows two ticks and no blue when read receipts are off — it does not guess. We are doing the same thing for SMS, and now there is a household example to say so with.

**Pitch line, if it comes up:** *"You already know how to read our delivery evidence — WhatsApp taught you. The difference is that ours is admissible."*

## 0.4.6 Screen-by-screen reference map

| Our screen | Open this | Because |
|---|---|---|
| **D9f Command Board** | incident.io incident page · Cloudflare overview | Aggregate-first, drill-down second |
| **D1f Live map** | Flightradar24 · Windy layer controls | Dense geography that stays readable |
| **D2f Status table** | Linear list view | Virtualised density without visual noise |
| **D10f Incident timeline** | incident.io timeline · GitHub PR timeline | Chronology with actors and state changes |
| **D11f Assistance queue** | PagerDuty incident list · Linear triage | Priority-ordered work with one-click assignment |
| **B8 Assurance ladder** | **WhatsApp ticks** · Stripe payment timeline | A learned tier model + per-step evidence |
| **F1 Quality gate** | **GitHub PR checks · Vercel deploy checks** | *"Merging is blocked — 1 check failed"* with the failing check **named** is exactly our pre-dispatch gate. Steal the pattern wholesale |
| **F3 Dual authorisation** | GitHub PR reviews (*"1 approval required"*) | A familiar, non-bureaucratic way to show a missing signature |
| **F2 Version chain** | GitHub releases · Notion page history | v1 → v2 → v3 with the reason for each change |
| **C6 Structured response** | **GOV.UK one-thing-per-page** · iOS Emergency SOS | One question, huge targets, no ambiguity |
| **C4 Safe zone** | Google Maps directions card | Destination + distance + one action |
| **D12f Decision explanation** | Stripe Radar risk breakdown | A score shown *with the factors that produced it* |

## 0.4.7 Accessibility is not a section here — it is the authority

The design authority for this product is **not** a games list and **not** a SaaS dashboard. It is:

1. **GOV.UK Design System** — the most rigorously tested public-service UI in existence.
2. **GIGW** (Guidelines for Indian Government Websites) and **WCAG 2.1 AA** — the statutory bar for anything a citizen touches.

➡️ **And the commitment that follows, which we should make out loud:**

> **SETU is built to pass PRAVESH** — our own sibling project, which audits Indian government sites against GIGW and WCAG. **We run it on ourselves and put the score on a slide.**

A life-safety console that failed its own team's accessibility auditor would be an unrecoverable question in Q&A. Passing it is a claim no other team in the room can make, and it costs us nothing but the discipline Part 11 already requires: contrast on every pairing, icon **and** text on every state, focus rings intact, `prefers-reduced-motion` honoured, 44px targets, and Dynamic Type that does not break the layout.

## 0.4.8 What we deliberately do not copy

Named so nobody has to relitigate them at 1 a.m.:

- **No generic-SaaS landing aesthetic** — gradient hero, glassmorphism, floating cards. Judges have seen a hundred this cycle and it reads as a template.
- **No Grafana density in the citizen app.** Ever.
- **No dark theme in the citizen PWA.** A dark screen at night, in a flood, reads as a dead phone.
- **No consumer-app gamification** — streaks, badges, confetti. Someone is being told to evacuate.
- **No emoji as iconography** anywhere. SVG icon set, one stroke weight (Part 11's `lucide-react`).
- **No novel navigation in the citizen app.** Familiarity beats cleverness when the user is scared.
- **No animation that does not carry information** (Part 0.5's rule, restated because it is the one most likely to erode).

---

# PART 0.5 — VISUAL DIRECTION: TOP-PLAYER-GRADE UI, READ BEFORE PART 0

**North star, in one line:** *a war-room HUD from a AAA strategy game, disciplined by GOV.UK's restraint* — never a ministry PDF turned into a webpage, never a neon gamer overlay with glow on everything. The demo is judged in six minutes; a console that looks like a Bootstrap admin template loses credibility before a single feature is shown, and a console that looks like a Discord bot's dashboard loses credibility for the opposite reason. This section sets the taste bar the Part 11 design tokens implement — read it first, then Part 11 is "how," this is "why."

### The two inputs, and how they combine

**From top games — steal the *feeling* of stakes and momentum, not the chrome:**

| Reference | What to actually borrow | What to leave behind |
|---|---|---|
| **Frostpunk / Cities: Skylines** | Dense, color-coded overlays on a live map; a single frozen/failing-district color read instantly across the whole board | Frostpunk's literal grime/soot texture — too grim for a public-sector tool |
| **XCOM 2's mission UI** | Angular, corner-cut panel shapes instead of default rounded rectangles for modals and cards — reads as "tactical," not "SaaS form" | The full sci-fi holograph overlay — too costume-y |
| **StarCraft II / RTS minimaps** | The instant, peripheral-vision read of "where is trouble" via a compact always-visible overview panel | Unit-count clutter — SETU's map has ~7,000 units, not 12 |
| **Apex Legends / Valorant kill-feed** | A live, streaming, one-line-per-event feed ("Wayanad block 12 acknowledged") — this is literally D1f's live table, staged as a feed instead of only a grid | The victory-royale fanfare/sound stingers — silence is correct here |
| **Mass Effect's codex/journal screens** | Calm, high-contrast blue-on-dark information density that still feels premium at rest, not just when something's happening | Full holographic 3D rotation gimmicks |
| **Warframe's star map** | Radial gauge/dial treatment for a single risk score (reach-risk, thunderstorm risk) — a dial reads faster than a number in a room of judges | Neon-on-every-surface — reserve glow for exactly one severity tier, see below |

**From government design systems — the restraint that keeps it credible, not decorative:**

GOV.UK Design System (already the reference for the sibling PRAVESH project's tokens) supplies the actual discipline: icon **and** text label on every state, never color alone; WCAG AA contrast on every pairing, no exceptions for the sake of mood; a "this is a prototype" phase-banner pattern used honestly rather than hidden. Borrow the *seriousness*, not the visual plainness.

### The rule that reconciles both lists: earn every flourish

Nothing gets a glow, a pulse, or a motion effect **unless it's carrying real information.** An `extreme`-severity badge gets a subtle ambient glow because extreme alerts *should* pull the eye. A `minor` badge never does. The live map's newly-dispatched-alert marker gets one radar-style expanding-ring pulse on arrival, then goes still. KPI numbers in the header strip count up over ~400ms when they change — motion as *confirmation*, not decoration, and `prefers-reduced-motion` collapses every one of these to instant, no exceptions.

### Signature beats worth building deliberately for the six minutes

- **The alert composer opens as an angular "mission briefing" panel**, not a centered modal with rounded corners.
- **The live delivery feed scrolls like a kill-feed** along one edge of the Live Operations screen, one line per acknowledgement as it lands.
- **The reach-risk overlay renders as a radial dial per flagged unit**, not a bare decimal.
- **The citizen PWA stays deliberately calmer than the console** — light, large-touch, close to zero animation. A panicking citizen should see something closer to a boarding pass than a war room.

### **[v3.0] Four new visual beats the operational-closure layer earns**

- **The Quality Gate reads as a pre-flight checklist, not an error toast.** Six rows, each with ✓/✗ and the exact failing reason. A blocked dispatch button with the reason *adjacent to it*, never a dismissible red banner the officer can click past. Failing a gate must feel like a seatbelt, not a nag.
- **The approval panel is the one place in the console that is deliberately, visibly incomplete until a second human acts.** `✓ Officer A / ☐ Officer B` with the empty checkbox rendered at full contrast, not greyed — the UI's job here is to make the missing signature the loudest thing on screen.
- **The Delivery Assurance Ladder renders as a five-rung vertical ladder per delivery, and the rungs a channel cannot prove are struck through with the words "Not applicable — this channel provides no such signal."** Not greyed out (reads as "loading"), not hidden (reads as "we didn't check"). Struck through with a reason is the only honest rendering, and it is the single most GOV.UK-correct component in the whole product.
- **A relayed alert in the citizen PWA carries a distinct provenance chip** — `⇄ Received via a nearby device · signature verified` — in the same visual family as the console's `SIM` badge. The citizen must never be unable to tell where their warning came from.

### Guardrails — the ways "sexy" goes wrong, named so nobody has to relearn them live

No gradient-heavy, glassmorphism, generic-SaaS-landing-page look. No full-screen color tinting on alert states — glow the badge, never wash the whole viewport red. No sound design in the judged demo. **[v3.0]** And one new guardrail: **no progress bar, spinner, or percentage may ever be shown for a signal the platform does not actually have.** An 88% that is really "88% of the tiers we can measure" must say so in the label. Every flourish still has to pass axe-core and the WCAG AA contrast check mandated in Part 11 and re-verified in Part 17's rehearsal day.

---

# PART 0 — THE ENGINEERING CONSTITUTION

Seven rules from v2.0/v2.1, **plus six [v3.0] rules that exist because the new layer introduces new ways to be dishonest.** Every PR is reviewed against all thirteen.

### Rule 1 — No magic values in code, ever
Every threshold, timeout, retry count, model weight, channel priority and severity cutoff lives in **`config` tables in Postgres** or in **environment variables**, never as a literal in a `.py` or `.ts` file.

```python
# ❌ BANNED
if minutes_since_sent > 15:
    escalate()

# ✅ REQUIRED
policy = await policy_repo.get_escalation_policy(alert.severity, channel.id)
if elapsed > policy.escalate_after_seconds:
    await escalate(policy.next_channel_id)
```

### Rule 2 — Every external system sits behind an interface
Channels (SMS/push/email/IVR/siren/**human relay**), alert sources, and geocoders are **adapters implementing a Protocol**, registered at runtime from a DB table. Adding a channel must require **zero changes to the delivery engine**.

### Rule 3 — No dataset is embedded in the repo as code
Village lists, phone numbers, translations, severity mappings, **relay node registries, channel capability matrices** are **seeded from data files or migrations into the DB**, never written as Python lists or TS objects.

### Rule 4 — Every number shown to a user is traceable
Any figure on any screen must resolve to a row with a `source_id`, `fetched_at`, and `checksum`. If it can't, it doesn't ship.

### Rule 5 — The demo path must run with the network cable unplugged
Not "should." Must. Tested every single day from Day 6 onward.

### Rule 6 — No claim without a measurement
We never say "94% accurate." We say "on our held-out set of N, precision was X, recall Y, and here is the confusion matrix." Where we cannot measure, we say **"this is a bootstrap model pending real-world data"** — out loud, in the UI and the pitch.

### Rule 7 — Feature freeze on 21 August, 21:00 IST
After that: bug fixes and rehearsal only. Enforced by `freeze-guard.yml` (Part 27), not by memory.

### **Rule 8 [v3.0] — A channel may never claim an assurance tier it cannot prove**
The five-rung assurance ladder is driven by a **`channel_capability` table** (Part 5), not by code. If `supports_opened_tier = false` for SMS, the UI renders *"Not applicable — this channel provides no such signal"* and the API returns `not_applicable`, never `false`, never `0`, never a blank. A missing signal and a negative signal are different facts and must never render identically. **CI test enforces this:** `test_no_channel_reports_unsupported_tier()`.

### **Rule 9 [v3.0] — Human-confirmed dissemination is never mixed with digital delivery evidence**
`relay_confirmation.confirmed_by_human` is a separate table, a separate event type, a separate UI treatment, and a separate column in every report. The sentence *"SMS delivered"* may never be rendered for what was actually *"a village officer confirmed physical dissemination."* Both are valuable; conflating them would destroy the audit ledger's entire reason to exist.

### **Rule 10 [v3.0] — Every automated decision stores the inputs that produced it, in the same transaction**
Reach-risk already does this (`reach_prediction.features`). v3.0 extends it: `assistance_case.priority_factors`, `alert_validation_result` per rule, `fatigue_evaluation.inputs`. A score with no stored inputs is a black box, and Part 23's "do not use an unexplained black-box score" is now a schema constraint (`NOT NULL`), not advice.

### **Rule 11 [v3.0] — An alert accepted from a nearby device is untrusted until its signature verifies**
Community Relay Mode creates a path where a payload reaches a citizen's screen without touching our server. Every alert is **Ed25519-signed server-side**; the PWA verifies against a public key in its bundle and **discards unverified payloads silently, logging locally**. A disaster-alert platform that could be used to inject a fake evacuation order over Bluetooth would be worse than no platform. This is not optional and not a stretch item.

### **Rule 12 [v3.0] — Human origin requires human approval; machine origin records machine provenance**
An officer-composed `severe`/`extreme` alert requires two distinct human approvals. An alert auto-ingested from USGS/GDACS is approved by `approval_provenance = 'authoritative_source'` — the seismograph *is* the second pair of eyes — and dispatches without waiting for a human. Neither path is a shortcut for the other, both are recorded in `alert_approval`, and Part 17.2 has the rehearsed answer for why.

### **Rule 13 [v3.0] — No new external dependency after Day 4**
v3.0's entire feature set is built on data already collected, channels already built, or browser APIs already in the target engine. Any proposal requiring a new verified data source, a new API key, or a new approval clock is **out of scope by construction**, and Part 35 records each one that was rejected on exactly this ground, with its reason. This is the rule that makes a 17-feature addition at Day 4 survivable.

---

# PART 1 — VERIFIED REALITY CHECK

**Read this section before writing a line of code.** Several widely-assumed facts are wrong, and discovering them on Day 9 would be fatal.

## 1.1 What is genuinely free (verified, two passes — unchanged from v2.1)

| Layer | Choice | Verified limits | Verified at |
|---|---|---|---|
| **Postgres + PostGIS** | **Neon** free | 0.5 GB/project, 100 CU-hours, 5 GB egress, **permanent, no card**, compute suspends after 5 min idle | `neon.com/pricing`, `neon.com/docs/extensions/postgis` |
| **Vector search (Copilot)** | **pgvector on Neon** | Available on every Neon plan, no add-on | `neon.com/docs/extensions/pgvector` |
| **Redis** | **Upstash** free | **500K commands/month**, 256 MB, 10 GB bandwidth, **no card**. Streams ✅ Pub/Sub ✅ GEO ✅ Sorted Sets ✅ Lua ✅ | `upstash.com/pricing` |
| **Push notifications** | **Firebase FCM** | **"No-cost" on Spark and Blaze** — unmetered | `firebase.google.com/pricing` |
| **Email** | **Brevo** (300/day) or Resend (100/day) | as stated | `brevo.com/pricing` |
| **Earthquake alerts** | **USGS Earthquake API** | live, global incl. India, **zero auth**, confirmed by direct fetch | `earthquake.usgs.gov/fdsnws/event/1/` |
| **Cyclone/flood/wildfire/drought** | **GDACS** | live JSON, global incl. India, **zero auth**, confirmed | `gdacs.org` |
| **Thunderstorm/convective risk** | **Open-Meteo** | free, no key for non-commercial, CAPE/LI/CIN global | `open-meteo.com/en/docs` |
| **Safe-zone / shelter locations** | **OSM Overpass API** | free, no auth, <10K queries/day courtesy limit | `wiki.openstreetmap.org/wiki/Overpass_API` |
| **Admin geometry** | **geoBoundaries gbOpen IND** | ADM3 6,836 units / ADM4 7,152, **ODbL 1.0, no auth**, ~39 MB | geoBoundaries raw GitHub |
| **Buildings** | **Google Open Buildings** | India covered, CC BY 4.0 or ODbL 1.0 | `sites.research.google/open-buildings/` |
| **Population** | **WorldPop** | ~100 m raster, CC BY 4.0 | `hub.worldpop.org` |
| **Terrain (DEM)** | **Copernicus GLO-30**, fallback **SRTM 30m** | no-sign-request S3; four-tile check in Part 29 | `registry.opendata.aws/copernicus-dem/` |
| **Cell towers** | **OpenCelliD** | CC BY-SA 4.0, free token, community-run | `opencellid.org/downloads.php` |
| **Translation model** | **`ai4bharat/indictrans2-en-indic-dist-200M`** | 0.3B params, MIT, CPU-feasible | HF model card |
| **Frontend host** | **Vercel Hobby** | non-commercial only | — |
| **API host** | **Render** free web service | spins down when idle, ~50 s cold start | `render.com/pricing` |
| **CI** | **GitHub Actions** | unlimited on public repos | — |

## 1.2 **[v3.0] What the new layer depends on — and why none of it is a new risk**

Per Rule 13, every new feature had to run on something already in the stack. Here is the full accounting, including the two places where the honest answer is "this capability does not exist and we say so":

| New feature | What it needs | Status |
|---|---|---|
| **B8 Delivery Assurance Ladder — push tiers** | FCM send response (provider ID) + **a callback from our own service worker** for device-delivered, + `notificationclick` for opened | ✅ No new dependency. **Critical correction:** FCM does **not** report device-delivery to the sender. The only real device-delivered signal for push is our own SW calling home. v2.1 implied otherwise; v3.0 builds the callback (Part 8.6). |
| **B8 — SMS tiers** | Twilio **status callback webhook** (`delivered`/`undelivered`/`failed`) | ✅ Already using Twilio for outbound; status callbacks are the same account, no extra cost, no extra approval. **This is a genuine carrier-confirmed signal — stronger than push's.** |
| **B8 — SMS "opened" tier** | A read receipt | ❌ **Does not exist.** No Indian carrier, and no carrier anywhere, exposes SMS read receipts to a sender. `channel_capability.supports_opened_tier = false`. Rendered "Not applicable". Rule 8. |
| **B8 — IVR tiers** | Twilio call-status webhook (`in-progress` = answered) + `<Gather>` DTMF | ✅ Same Twilio account. **`in-progress` is the strongest "a human received this" signal in the entire platform** — better than push or SMS, because a human physically answered. |
| **B8 — siren tiers** | Any receipt from a physical siren | ❌ **Does not exist.** A siren is fire-and-forget. Everything above `provider_accepted` is `not_applicable`; only B9's human confirmation can close the loop. Rule 9. |
| **B9 Trusted Human Relay** | An outbound IVR call to a registered relay node + one DTMF keypress | ✅ Reuses the IVR adapter and Twilio trial. Seeded relay nodes are our own data (Rule 3). |
| **B10 Community Relay Mode** | **Web Bluetooth GATT** (`navigator.bluetooth`) + existing IndexedDB cache + Ed25519 verify | ⚠️ **Chromium-only.** Web Bluetooth is supported in Chrome/Edge on Android and desktop; **not supported in iOS Safari, and not on Firefox.** This is the *same* platform weakness v2.1 already flagged for the offline PWA (Part 11.4). Mitigation is identical: **present on Android, decided by Day 8.** Signing uses `PyNaCl` server-side and `WebCrypto`/`@noble/ed25519` client-side — both free, both offline. |
| **C6 Structured Emergency Response** | Nothing external | ✅ Buttons + a table + the existing idempotent-POST pattern. |
| **D7f Reachability Score** | `admin_unit.population` (WorldPop, already loaded) + `delivery` rows | ✅ A view. Zero new data. |
| **D8f Communication Vulnerability Map** | `unit_features` (already computed for the reach-risk model) | ✅ A view. Zero new data. Degrades honestly if OpenCelliD slipped (Part 30). |
| **D13f Warning Lead-Time Analytics** | An estimated hazard onset time | ⚠️ **Partial by physics, not by engineering.** GDACS and Open-Meteo carry forecast onset; **USGS earthquakes do not — a quake has no forecast lead time.** `alert.estimated_onset_at` is nullable; the view reports lead time only where non-null **and publishes its own coverage %**. Rendering a lead time for an earthquake would be meaningless, so we don't. |
| **E4 Citizen Enrollment** | Twilio **inbound** SMS webhook + a CSV upload form | ✅ Same Twilio number. Inbound is free to receive on the trial. |
| **F1–F4 Governance layer** | Nothing external | ✅ Pure application logic + config rows. |

**Nothing in the table above requires a new API key, a new registration, a new approval clock, or a new verified dataset.** That is the single most important property of this release and the direct consequence of Rule 13.

## 1.3 ⚠️ The traps — verified, carried forward unchanged from v2.0/v2.1

**Trap 1 — Render's free Postgres dies after 30 days.** Use Neon. (Supabase pauses free projects after 1 week idle; Neon merely suspends compute after 5 min.)

**Trap 2 — The IMD API is NOT public. Every endpoint returns 401.** Not gating anything: USGS + GDACS are confirmed live, zero auth. Register anyway on Day 1 — a strict upgrade if it clears.

**Trap 3 — SACHET has no documented alert-discovery feed.** `FetchXMLFile?identifier=` is confirmed; discovery is `[UNVERIFIED]`. Built behind the same adapter interface; ships only if discovery is found.

**Trap 2a — USGS + GDACS close the gap Traps 2 and 3 leave open.** Confirmed live, zero auth. **This is the primary ingestion source.**

**Trap 8 — Neither USGS nor GDACS covers thunderstorms.** We compute one: Open-Meteo CAPE + Lifted Index + CIN → Model 5 (Part 9.5).

**Trap 9 — The evacuation-route feature had no data source.** Resolved: OSM Overpass → `safe_zone` table (Part 4.6).

**Trap 10 — IndicTrans2's 1B model needs a GPU.** Switched to the 200M distilled variant.

**Trap 4 — Nationwide village polygons don't fit a free database.** ADM5 = 649,771 polygons = 1.01 GB; Neon free is 0.5 GB. **ADM3 nationwide (~39 MB) + ADM5 for Kerala & Maharashtra only.** A scoping decision, stated in the pitch.

**Trap 5 — Free SMS to arbitrary Indian numbers does not exist. At all.** Twilio trial: 100 SMS, verified recipients only, expires in 30 days. India domestic requires **TRAI DLT registration** (~10 business days, requires a registered legal entity). ➡️ **FCM push is PRIMARY. SMS is a fully-implemented adapter running against a Twilio trial for 2–3 verified numbers, and a `SimulatedCarrierAdapter` for everything else.** Said out loud in the pitch (§8.5).

**Trap 6 — GADM is legally unusable** (no redistribution). Use geoBoundaries (ODbL).

**Trap 7 — datameet/maps has no village boundaries.** Use geoBoundaries.

### **[v3.0] Trap 11 — `pgp_sym_encrypt` output is non-deterministic, so you cannot dedupe encrypted phone numbers with a UNIQUE index.**

This one would have been discovered on Day 7, at the worst possible moment: the second run of a CSV import silently doubling every recipient in a district, inflating the Reachability Score denominator, and corrupting the one metric the pitch leads with.

`recipient.phone_enc BYTEA` (v2.1, Part 5) is encrypted with `pgcrypto`'s `pgp_sym_encrypt`, which is **randomized by design** — encrypting the same number twice produces two different ciphertexts. `UNIQUE (phone_enc)` therefore never fires, and `ON CONFLICT DO NOTHING` never triggers.

➡️ **Fix, shipped in the Day 4 migration:** add a deterministic, indexable `phone_hash` column alongside the recoverable ciphertext.

```sql
ALTER TABLE recipient ADD COLUMN phone_hash BYTEA;
-- HMAC with a server-side pepper, NOT a bare sha256 — a bare hash of a 10-digit
-- Indian mobile number is brute-forcible in seconds (10^10 keyspace).
-- Pepper lives in PHONE_HASH_PEPPER (Part 25), never in git, never in the client.
CREATE UNIQUE INDEX recipient_phone_hash_uix ON recipient (phone_hash)
  WHERE phone_hash IS NOT NULL;
```
```python
def phone_hash(phone_e164: str) -> bytes:
    return hmac.new(settings.phone_hash_pepper.encode(), phone_e164.encode(), hashlib.sha256).digest()
```
`phone_enc` stays for the (audited, officer-only) reveal path in Part 12. `phone_hash` is what dedupe, enrollment, and STOP-keyword lookups use. **Never log `phone_hash`** — it is a stable pseudonymous identifier, i.e. still personal data under any reasonable reading.

### **[v3.0] Trap 12 — Web Bluetooth cannot be initiated without a user gesture, and cannot run in the background.**

A naive reading of Community Relay Mode is "Person A's phone automatically finds nearby phones and pushes the alert." **That is not possible in a browser.** `navigator.bluetooth.requestDevice()` **requires a user gesture** (a tap) and shows a **browser-controlled device chooser** the page cannot skip or style. There is no background BLE scanning from a PWA on any engine.

➡️ **Design consequence, not a workaround:** Community Relay is an **explicitly citizen-initiated act**, and the UI is honest about that — a prominent *"Share this alert with someone nearby"* button on a received alert, which the citizen taps. This is arguably better product design than silent background relay (a person choosing to warn their neighbour), and it is the only version that can actually exist. **The pitch language is "one-tap peer relay," never "automatic mesh."** Recorded here so nobody builds toward an impossible spec and discovers it on Day 7.

### **[v3.0] Trap 13 — the Twilio trial is *credit*-metered, not just message-capped, and v3.0 added two features that make real voice calls.**

v2.0's Trap 5 correctly bounded SMS: 100 messages, verified recipients only, 30-day expiry. It said nothing about **voice**, because v2.1 had no voice feature on the critical path. v3.0 promoted **B6 (IVR)** to core and added **B9 (human relay)** — both of which place **real outbound calls**, billed **per minute from the same finite trial credit** as the SMS.

The arithmetic nobody had done:

| Consumer | Unit cost | Demo need | Rehearsal need (Day 12–13) |
|---|---|---|---|
| SMS out | 1 message | 1 (the "real SMS in the room" beat) | ~10 across six run-throughs |
| SMS status callbacks | **free** (inbound webhook) | — | — |
| SMS inbound (E4 `REGISTER`/`STOP`) | **free to receive** | 1 | ~5 |
| **IVR outbound (B6)** | **per-minute voice** | 1 call | ~6 |
| **Relay call (B9)** | **per-minute voice** | 1 call | **10× — Part 16 requires the relay beat rehearsed 10 times** |

**Trial credit is a fixed sum, not a per-service allowance.** Ten rehearsals of the relay beat plus six IVR calls plus a dozen test SMS is genuinely within a standard trial credit, but it is **not** comfortable, and burning it on Day 12 with the demo on Day 14 would leave the two most impressive new beats unable to run live.

➡️ **Mitigations, all three mandatory:**
1. **Rehearse B6 and B9 against `SimulatedCarrierAdapter` by default.** Only the *final* two rehearsals of each use real Twilio. The state machine, DTMF parsing, `relay_confirmation` write and UI are identical on both paths — the only untested thing on the simulated path is Twilio's own reliability, which is not what we are rehearsing.
2. **Part 28's counter check covers voice minutes, not just SMS count.** The check is `credit remaining`, read from the Twilio balance API before every real-call test from Day 18.
3. **Create the account ≈18 Aug** (30-day expiry, Trap 5) and **top up nothing** — if credit runs out, the demo degrades to the simulated path with its `SIM` badge, which is honest and already rehearsed. **We never pay to make a demo beat work.** Rule 13's spirit: a feature that needs money to demonstrate is a feature we present from the recording instead.

**One `[RECONFIRM]` for Day 5, before B6/B9 become load-bearing:** outbound **voice** to Indian mobile numbers from a trial account. Twilio's Indian *voice* regulations differ from its SMS/DLT rules, and acquiring an Indian phone number requires a regulatory bundle with address proof — which a student team does not have. Calling *to* verified Indian mobiles from a non-Indian trial number is the path we assume works; **verify it with one real call on Day 5**, and if it does not, B6 and B9 run entirely on the simulated adapter with the `SIM` badge and the honest sentence already written for SMS. Neither feature's logic, schema or UI changes either way.

---

## 1.4 The Upstash command budget — re-derived for v3.0

**500,000 commands/month ≈ 16,600/day.** v2.1 measured **~150–300 commands per full alert run**. The new layer's Redis cost, itemised:

| New operation | Redis cost | Why it's this cheap |
|---|---|---|
| Assurance-ladder events | **0** | `delivery_event` is Postgres. Redis holds only the hot queue (v2.1 §1.3 principle, unchanged). |
| Structured citizen responses | **0** | Postgres write + the *existing* throttled aggregate publish. |
| Assistance queue ordering | **1–2 ZADD per alert run** | One `ZADD` per batch of new cases, not per case — same batching discipline as §6.2. |
| Command Board live tiles | **0 additional** | Subscribes to the *existing* `setu:v1:chan:alert:{id}` throttled channel (max 1 publish/sec, already budgeted). A second subscriber costs the publisher nothing. |
| Fatigue evaluation | **0** | A Postgres `COUNT` over `delivery`, not a Redis counter. |
| Relay task dispatch | **~1** | One extra delivery enqueued into the existing batched stream. |
| Alert versioning / supersede | **~1** | One `ZREM`-equivalent cleanup of superseded retries. |

**Revised worst case: ~305–310 commands per full alert run** (from ~300). At 310/run, the daily budget supports **~53 full runs/day**. v2.1's "50+ runs/day with headroom" claim survives, but the headroom is now thinner and must not be hand-waved:

➡️ **Two enforcement additions:** (1) The Part 28 monitor's 80% threshold (13,280) stands unchanged and is now the *primary* guard, not a nice-to-have. (2) **Development uses local Redis in Docker, unconditionally** — this was already the rule in v2.1 and it is now load-bearing. Any teammate pointing `REDIS_URL` at Upstash for local iteration can burn a day's budget in an afternoon of testing; Part 28's demo-day runbook re-checks the counter at T-30 min.

---

## 1.5 **[v3.0] THE COMPLETE TECHNOLOGY STACK — every runtime dependency, what it does, and why it is that one**

§1.1 lists the *hosted services* and §1.2 lists what the new features depend on. Neither lists the **libraries**, and a spec that says "FastAPI" seven times without ever stating the version policy is a spec with a loose end. This is that table. **Anything not on this list should not appear in a `requirements.txt` or a `package.json`** — the same rule Part 25 applies to environment variables.

**Version policy, stated once:** every Python dependency is pinned exactly in `requirements.txt` (`pip freeze` output, committed); every JS dependency is locked via `package-lock.json`. **No range specifiers anywhere.** A transitive upgrade of a transformer library on 23 August is not a risk worth carrying for the convenience of a caret.

### 1.5.1 Backend — Python 3.11

| Library | Used for | Why this one |
|---|---|---|
| **FastAPI** | The whole API surface (Part 10), RBAC dependencies (Part 26), OpenAPI docs for free | Async-native, and its dependency-injection system is what lets Part 26's permission matrix be *one decorator per route* rather than a check inside every handler |
| **Pydantic v2** | Request/response schemas, input validation on every endpoint | Malformed input returns 422 and **never reaches a DB query**. Also where C6's free-text length cap lives (§12.1) |
| **Uvicorn** (+ `uvloop`) | ASGI server | Standard; `uvloop` matters because the delivery worker is I/O-bound on provider HTTP calls |
| **asyncpg** via **SQLAlchemy 2.x async** | All Postgres access, connection pooling against the Neon **pooled** URL (Part 23) | `create_async_engine(POOLED_URL, pool_size=10, ...)` — Part 23's whole fix is one line of SQLAlchemy config. Raw asyncpg for the hot delivery loop, ORM-free |
| **Alembic** | The six migrations `0007`–`0012` (§5.13), run against the **direct** URL | Transaction-mode pooling breaks session-level DDL — which is exactly why Part 23 splits the two URLs |
| **redis-py** (async) | Streams, consumer groups, ZSETs, pub/sub (Part 6) | Full Streams + `XAUTOCLAIM` support, which §6.3's crash-safety depends on |
| **httpx** | Every outbound fetch: USGS, GDACS, Open-Meteo, Overpass, FCM, the HF Space | Async, with real timeout semantics. Every call site passes an explicit timeout from config — a default-timeout HTTP client is how an ingestion poller hangs forever |
| **APScheduler** | The ingestion poll loop, the nightly Overpass refresh, `safe_zone` reseeding | In-process, no extra service, no extra cost |
| **lxml** | Defensive CAP 1.2 parsing (§4.4) | 36 state authorities implement CAP independently; we need a parser that survives malformed XML and tells us *why* it failed, for the quarantine reason |
| **shapely** + **pyproj** | CAP circle→polygon conversion, geometry sanity checks before they reach PostGIS | The quality gate's `geometry_non_empty` rule (Part 21) runs here, before a bad polygon becomes a bad `ST_Intersects` |
| **rasterio** | WorldPop population and DEM raster sampling per admin unit | Build-time only — never in the request path |
| **pgcrypto** *(Postgres extension)* | `phone_enc` / `email_enc` at rest (Part 12) | In-database encryption; the key never leaves the server env. **Its randomized output is Trap 11**, which is why `phone_hash` exists alongside it |
| **PyNaCl** | **[v3.0]** Ed25519 alert signing (Rule 11, §8.7) | ~2 MB, **zero Torch dependency** — which is why signing stays on the Render API service rather than the HF Space (Part 22). Putting a 50-second cold start in the dispatch path would have been a self-inflicted wound |
| **LightGBM** | Reach-risk model (§9.2) and the future thunderstorm classifier upgrade | A boosted-tree model is a few MB — genuinely fine inside Render's 512 MB, unlike a transformer. This is the reason Part 22's split works at all |
| **slowapi** | Per-IP and per-token rate limiting, tighter on `/dispatch` (Part 21) | **[v3.0]** now also guards the three new public POST surfaces: SW receipts, SMS-inbound, peer-relay receipts (§12.1) |
| **twilio** (SDK) | SMS out, SMS status callbacks, IVR calls, `<Gather>` DTMF, inbound SMS keywords | Five consumers on one trial account — **Risk #8, raised in v3.0 for exactly this reason** |
| **firebase-admin** | FCM push send + OAuth token minting | |
| **structlog** | Structured logging with the PII redaction filter (Part 12) | **[v3.0]** `phone_hash` added to the redaction list — a stable pseudonymous identifier is still personal data |
| **prometheus-fastapi-instrumentator** | The metrics in Part 14, including v3.0's seven new ones | |
| **sentry-sdk** | Error tracking, `beforeSend` strips PII | Disabled during Locust runs (Part 28) — load-test errors are expected, not diagnostic, and would burn a month's quota in an afternoon |

### 1.5.2 ML service — its own Hugging Face Space (Part 22)

| Library | Used for | Note |
|---|---|---|
| **PyTorch** (CPU build) | Inference runtime for both transformers | **CPU wheel only.** The CUDA wheel is ~2 GB of pointless download on a CPU-only host |
| **transformers** | IndicTrans2 200M translation (§9.3) | The **distilled 200M**, not the 1B — Trap 10 |
| **sentence-transformers** | `paraphrase-multilingual-MiniLM-L12-v2` for dedup embeddings (§9.1) | |
| **IndicTransToolkit** | IndicTrans2's required pre/post-processing | Easy to miss; the model's output is wrong without it |
| **optimum** / **bitsandbytes** | int8 quantization **fallback only** | Part 22 step 6: if HF free hardware is smaller than remembered, quantize — never silently ship the OOM-prone topology |

**`services/api` imports none of the above.** That separation is a Part 33 checklist item and a CI grep, not a convention.

### 1.5.3 Frontend — TypeScript, two apps, one token package

| Library | Used for | Why |
|---|---|---|
| **React 18** + **TypeScript** | Both the console and the citizen PWA | |
| **Vite** | Build tool for both apps | Fast rebuilds matter when you are iterating on a demo for ten days. Also where `ALERT_SIGNING_PUBKEY_B64` is injected as a build-time constant (Part 25) |
| **TanStack Query** | **Every** data fetch in the console | Removes a whole class of loading-state and race-condition bugs *before they can be written* — which is why v2.1 mandated it from the first API call rather than retrofitting |
| **TanStack Virtual** | The 7,000-row status table at 60 fps (§11.3) | |
| **MapLibre GL JS** + **pmtiles** | The live choropleth map and the D8f vulnerability layer | Open-source, no API key, no per-load billing. **Tiles are a self-hosted `.pmtiles` file (§1.6.5), not a hosted service** — a hosted basemap goes blank when the presenter unplugs the network |
| **Tailwind CSS** | Styling both apps, driven by `packages/tokens` | **Semantic tokens only, never raw hex in a component** (§11.1). The contrast gate checks every pairing in the Tailwind config |
| **lucide-react** | Every icon in the token tables (§11.1) | Each severity/state/tier carries an icon **and** a text label — never colour alone |
| **Workbox** | Service worker: `NetworkFirst` alert caching, and the **four** `BackgroundSyncPlugin` queues — acks, C6 responses, B8 receipts, B10 peer receipts (§11.4) | The offline story *is* Workbox. All four queues must survive a cable pull; that is Gate 3 |
| **@noble/ed25519** | **[v3.0]** Client-side signature verification before an alert renders (Rule 11) | Tiny, audited, zero-dependency, and **works offline** — which is the entire point: a device with no network still verifies authenticity |
| **idb** | IndexedDB wrapper for the offline alert store and peer-relay inbox | |
| **Web Bluetooth API** *(browser built-in)* | **[v3.0]** B10 peer relay transport (§8.7) | **Chromium-only — not iOS Safari, not Firefox.** Same weak spot as the offline PWA, which is why the Day-8 device decision covers both (Risk #4 + #15) |
| **Recharts** | Analytics and lead-time percentile charts | |

### 1.5.4 Testing, tooling, CI

| Tool | Used for |
|---|---|
| **pytest** + **pytest-asyncio** + **pytest-cov** | Unit/integration; the **95% branch floor on `state_machine.py`** |
| **Hypothesis** | The 4 v2.1 property tests + **[v3.0] 5 new ones** (Part 13) — the honesty invariant, the quorum invariant, ladder monotonicity under out-of-order webhooks, signature tampering, CSV idempotency |
| **Playwright** | E2E incl. the offline path; compose → validate → approve ×2 → dispatch → respond → assign |
| **Locust** | Load: 7,000 units, 50 WS clients, **[v3.0] + a 340-callback webhook burst** (Part 23) |
| **testcontainers** / docker-compose | Ephemeral Postgres+PostGIS + Redis for integration runs |
| **ruff** + **black** + **mypy** | Lint, format, types on `delivery`, `ml`, **[v3.0] `governance`, `response`** |
| **gitleaks** / **detect-secrets** | Pre-commit + CI secret scanning |
| **pip-audit** / **npm audit** | CVE gate on every push |
| **Custom CI scripts** | `check_no_hardcoding.py` (Part 32) · `check_env_example.py` (Part 25) · **[v3.0] `check_channel_capability.py`** (Part 13, Rule 8) |
| **GitHub Actions** | ci · deploy · keepalive · snapshot · **freeze-guard** (Part 27) |

### 1.5.5 What this stack deliberately does **not** contain

Naming the absences is as useful as naming the choices, and each of these was a real decision:

- **No Kubernetes, no Terraform, no message broker beyond Redis.** Six people, ten days, ₹0. Redis Streams with a consumer group gives at-least-once delivery, which is the only queue guarantee that matters here (§6.3).
- **No Kafka.** The Upstash command budget (§1.4) is the actual constraint, not throughput. A broker would add an operational surface with no free tier that survives the project.
- **No ORM in the delivery hot path.** `state_machine.py` uses raw SQL with `FOR UPDATE` because the row-lock semantics are the correctness argument, and hiding them behind an ORM would hide the thing being tested.
- **No new ML framework in v3.0.** Seventeen features, zero new models (Part 9) — the "intelligence" features are config-weighted formulas whose inputs are stored (Rule 10).
- **No native mobile app.** A PWA is installable, offline-capable, and costs no app-store review cycle. The price is Web Bluetooth's Chromium-only support (§8.7) and iOS's weaker offline story — both disclosed, both covered by one device decision.
- **No paid tier of anything.** Rule 13's practical enforcement: every row above is free, open-source, or free-tier-permanent.

---

## 1.6 **[v3.0] DATA ACQUISITION: THE EXACT ENDPOINT, LICENCE, COMMAND AND TARGET FOR EVERY SOURCE**

§1.1 says *what* is free and §1.2 says *what the new features need*. Neither tells a teammate **how to actually get the bytes onto disk and into a table** — which means Phase 1's "load ADM3 nationwide + ADM5 for two states" was, until now, a sentence rather than a task. This section closes that.

**Honesty convention, same as the rest of this document:** endpoints marked **[RECONFIRM]** are ones whose exact path or parameter set should be verified in the first hour before being trusted; the *service* is confirmed live in §1.1, only the precise URL shape carries the marker. Anything marked **[UNVERIFIED]** has no confirmed automated access and carries a stated manual fallback.

### 1.6.1 Live alert sources — polled at runtime, never stored as files

| Source | Endpoint | Auth | Licence | Target |
|---|---|---|---|---|
| **USGS earthquakes** | `GET https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={iso}&minlatitude=6&maxlatitude=38&minlongitude=68&maxlongitude=98` | **None** | Public domain (US Gov) | `alert` via `UsgsAdapter` |
| **GDACS multi-hazard** | `GET https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP` **[RECONFIRM** exact query params — the *service* is confirmed live, the parameter set should be re-read from a live response on Day 4**]** | **None** | Free reuse with attribution (EC/JRC) | `alert` via `GdacsAdapter` |
| **Open-Meteo convective indices** | `GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=cape,lifted_index,convective_inhibition,precipitation_probability` | **None** (no key, non-commercial) | CC BY 4.0 | Model 5 → synthetic `alert` |
| **Open-Meteo precipitation** (reach-risk feature) | same host, `hourly=precipitation` | None | CC BY 4.0 | `unit_features` refresh |
| **SACHET** *(stretch, A7)* | `GET https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier={id}` — fetch confirmed; **discovery `[UNVERIFIED]`** | None | Govt. of India public feed | `alert` via `SachetAdapter`, only if discovery is found |
| **IMD** *(stretch, A7)* | `https://api.imd.gov.in/public/` — **all endpoints return 401** (Trap 2). Register at `api.imd.gov.in/public/register.php` | Required, not granted | — | Not on the critical path |

**Ingestion touches the network at runtime; nothing above is a build-time download.** Every adapter's unit tests run against **saved fixtures**, not the live network (base-spec Phase 1 rule) — so a CI run on a plane still passes.

### 1.6.2 Build-time geospatial downloads — fetched once, loaded into PostGIS

```bash
# ═══ 1. ADMIN BOUNDARIES — geoBoundaries gbOpen, ODbL 1.0, no auth ═══
# ADM3 nationwide (~38 MB simplified) — the Trap 4 decision.
# [RECONFIRM] path shape at github.com/wmgeolab/geoBoundaries before trusting the exact URL.
GB=https://raw.githubusercontent.com/wmgeolab/geoBoundaries/main/releaseData/gbOpen/IND
curl -fSL -o data/raw/ind_adm3.geojson \
  "$GB/ADM3/geoBoundaries-IND-ADM3_simplified.geojson"
# ADM5 village-level for the two case-study states ONLY (Trap 4: 649,771 polygons = 1.01 GB
# nationwide does NOT fit Neon free). Download national, filter before load.
curl -fSL -o data/raw/ind_adm5.geojson \
  "$GB/ADM5/geoBoundaries-IND-ADM5_simplified.geojson"

# Load ADM3, reprojected to 4326, simplified with the tolerance from config (§4.1).
ogr2ogr -f PostgreSQL "$DATABASE_URL_DIRECT" data/raw/ind_adm3.geojson \
  -nln admin_unit_stg_adm3 -t_srs EPSG:4326 -lco GEOMETRY_NAME=geom -overwrite

# Filter ADM5 to Kerala + Maharashtra BEFORE loading — this is the line that keeps
# the database inside 0.5 GB. Loading national ADM5 first will exceed Neon free.
ogr2ogr -f PostgreSQL "$DATABASE_URL_DIRECT" data/raw/ind_adm5.geojson \
  -nln admin_unit_stg_adm5 -t_srs EPSG:4326 -lco GEOMETRY_NAME=geom -overwrite \
  -where "shapeGroup='IND' AND ADM1_NAME IN ('Kerala','Maharashtra')"   # [RECONFIRM] attribute names

# ═══ 2. POPULATION — WorldPop constrained 100 m, CC BY 4.0, no auth ═══
# [RECONFIRM] exact filename at hub.worldpop.org/geodata/listing?id=29
curl -fSL -o data/raw/ind_pop.tif \
  "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/IND/ind_ppp_2020_UNadj_constrained.tif"
# Zonal sum per admin unit → admin_unit.population  (rasterio, build-time only, §1.5.1)
python scripts/load_population.py --raster data/raw/ind_pop.tif --level 3
python scripts/load_population.py --raster data/raw/ind_pop.tif --level 5

# ═══ 3. BUILDINGS — Google Open Buildings, CC BY 4.0 or ODbL 1.0 ═══
# Distributed as CSV.gz per S2 cell; download only the cells covering our two districts.
# [RECONFIRM] cell IDs + current download host at sites.research.google/open-buildings/
python scripts/load_buildings.py --district wayanad --district palghar
# → admin_unit.building_count

# ═══ 4. TERRAIN — Copernicus GLO-30 (no-sign-request S3), SRTM 30m fallback ═══
# The FOUR tiles that actually matter (Part 29) — not a national scan.
for tile in N11_00_E076_00 N19_00_E072_00 N19_00_E073_00 N11_00_E077_00; do
  aws s3 ls --no-sign-request \
    "s3://copernicus-dem-30m/Copernicus_DSM_COG_30_${tile}_DEM/" \
    && echo "OK: $tile" || echo "MISSING: $tile — SRTM for this cell only"
done
aws s3 cp --no-sign-request --recursive \
  "s3://copernicus-dem-30m/Copernicus_DSM_COG_30_N11_00_E076_00_DEM/" data/raw/dem/
# SRTM fallback (56°S–60°N, India fully inside): OpenTopography or NASA Earthdata.
# → unit_features.terrain_ruggedness, mean_elevation_m

# ═══ 5. CELL TOWERS — OpenCelliD, CC BY-SA 4.0, FREE TOKEN REQUIRED ═══
# India spans MCC 404 AND 405 — both are needed. Missing 405 silently halves tower counts
# across large parts of the country, which would quietly corrupt D8f's vulnerability map.
for mcc in 404 405; do
  curl -fSL -o "data/raw/cells_${mcc}.csv.gz" \
    "https://opencellid.org/ocid/downloads?token=${OPENCELLID_TOKEN}&type=mcc&file=${mcc}.csv.gz"
done
python scripts/load_towers.py            # → unit_features.tower_count_5km, nearest_tower_km
# If the token has not arrived: Part 30's 5-feature fallback. The view returns
# 'unknown_connectivity_features_pending', NEVER 'standard' (Part 30's whole point).

# ═══ 6. SAFE ZONES — OSM Overpass, ODbL 1.0, no auth ═══
# Nightly refresh job, NOT queried live per request (§4.6). Send a distinct User-Agent —
# their documented courtesy requirement. Stay under 10K queries/day, 1 GB/day.
python scripts/load_safe_zones.py --area IN     # → safe_zone

# ═══ 7. TRANSLATION MODEL — IndicTrans2 200M, MIT, gated by terms acceptance (free) ═══
# Runs on the HF SPACE, not on Render (Part 22). Downloaded at Space build time.
huggingface-cli download ai4bharat/indictrans2-en-indic-dist-200M
huggingface-cli download sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### 1.6.3 The one join key with no confirmed automated source

**LGD codes** (`admin_unit.lgd_code`) are the Local Government Directory identifiers used to join CAP `geocode` values to our geometry (§4.4's third geometry branch). They come from `lgdirectory.gov.in`, which offers **interactive downloads, not a documented public API — `[UNVERIFIED]` for automated access.**

**Fallback, and why it costs nothing:** `lgd_code` is `NULL`-able and **nothing on the critical path needs it.** Every alert we actually ingest (USGS, GDACS, our own nowcast, manual) carries **geometry**, so targeting uses `ST_Intersects` and never touches LGD. The code is only needed for CAP alerts that supply *geocodes instead of polygons* — i.e. SACHET/IMD, which are already stretch-track. **If SACHET never connects, LGD is never needed.** Recorded so nobody spends Day 5 scraping a directory for a column no live code path reads.

### 1.6.5 **The basemap — the data source that was missing entirely, and why it must be self-hosted**

**MapLibre GL renders nothing without map tiles**, and §1.5.3 listed MapLibre as "no API key" — true of the *renderer*, silent about the *tiles*. Until now the only reference to a tile source anywhere in this document was `basemaps.cartocdn.com`, dropped into a CSP header in Part 37 with no licence note, no quota note, and no entry in this section. Three features need tiles: **D1f live map, D8f vulnerability layer, A3 composer.**

**And there is a much bigger problem than picking a provider.** Every hosted tile service — CARTO, OpenFreeMap, MapTiler, OSM's own raster tiles — is an **HTTP call to somebody else's server.** Which means:

> **At 4:45 in the demo script, when the presenter unplugs the network, a hosted basemap goes blank.** The live map — the centrepiece of the offline beat, the thing the Wayanad story is told over — would render a grey void with coloured polygons floating on nothing. Gate 3 says *"the demo path must run with the network cable unplugged"*; a hosted basemap silently violates it, and it would be discovered on stage.

➡️ **Therefore the basemap is a build-time download, self-hosted, exactly like every other dataset in §1.6.2.**

```bash
# ═══ BASEMAP — Protomaps PMTiles, OpenStreetMap data, ODbL 1.0, no auth, no key ═══
# A single .pmtiles file MapLibre reads directly via the pmtiles:// protocol.
# We extract ONLY the two case-study districts + a low-zoom India overview, which keeps
# the file small enough to commit alongside the demo snapshot.
# [RECONFIRM] current extract tooling + build URL at protomaps.com / docs.protomaps.com
pmtiles extract https://build.protomaps.com/{date}.pmtiles data/raw/setu-basemap.pmtiles \
  --bbox=74.5,10.8,77.0,12.2 --maxzoom=12     # Wayanad + Kerala approach
pmtiles extract https://build.protomaps.com/{date}.pmtiles data/raw/palghar.pmtiles \
  --bbox=72.6,19.3,73.4,20.2 --maxzoom=12     # Palghar
# Served as a static file by Vite in dev and by Vercel in the demo — no tile server to run.
```
```ts
// web/console/src/map.ts — the protocol registration that makes it work offline
import { Protocol } from 'pmtiles';
maplibregl.addProtocol('pmtiles', new Protocol().tile);
// style.sources.basemap.url = 'pmtiles:///tiles/setu-basemap.pmtiles'
```

| Property | Value |
|---|---|
| **Licence** | OpenStreetMap data under **ODbL 1.0** — the same licence as geoBoundaries and `safe_zone`, already attributed in the footer |
| **Cost** | **₹0.** No key, no account, no quota — it is a file on disk |
| **Offline** | **Works with the cable unplugged**, which is the entire reason for this choice |
| **Attribution** | "© OpenStreetMap contributors" in the map corner — required, and already in the token package |

**Fallback, and it is a *convenience* fallback only:** **OpenFreeMap** (`openfreemap.org`) serves free MapLibre vector tiles with no key and no quota, and is a perfectly good source for **local development** where nobody is testing the offline path. It is explicitly **not** what the demo runs on. `app_config` carries `map.tile_source` = `pmtiles_local` | `openfreemap` so switching is a config row, not a code change — and the Day-11 snapshot verification asserts it reads `pmtiles_local`.

**This is the third time in this document that "confirm the offline path" caught something a reviewer would have missed** — after the snapshot table list (Risk #20) and the FCM device-receipt gap (§1.2). The pattern is worth naming: *anything that renders during the unplugged beat must be a file, not a request.*

### 1.6.4 Everything that is *our own* seed data, not a download

Per Rule 3, these are `data/seeds/*.sql`, committed, reviewable, never Python lists:

| Seed file | Contents | Provenance |
|---|---|---|
| `app_config.sql` | 38 v2.1 rows + **36 v3.0 rows** (Part 21) — every threshold with a `note` | Our design decisions |
| `channel.sql` | 8 channel rows incl. `human_relay`, `community_relay` | Our design |
| `channel_capability.sql` | **The Rule 8 honesty table** (§8.2) — 8 rows, each `not_applicable_reason` written to be read aloud | Our design + verified provider limits |
| `escalation_policy.sql` | 16 policy rows across 4 severities (Part 21) | Our design |
| `relay_nodes.sql` | 6 demo relay nodes, real institution types, **team members' verified phones** (§4.7) | Ours, disclosed in the pitch |
| `recipients_demo.csv` | Demo recipients — **generated numbers only**, never real PII (Part 12) | Generated |
| `alert_source.sql` | 6 source rows with `is_authoritative` set per Rule 12 | Our design |

**The `is_authoritative` column is the one row-level decision in this table worth re-reading:** USGS and GDACS `true`, `manual` and **`thunderstorm_nowcast` `false`** — our own model does not authorize its own extreme alerts (§9.5).

---

# PART 2 — PRODUCT SPECIFICATION

## 2.1 Personas

| Persona | Who | Primary need |
|---|---|---|
| **P1 — District Emergency Officer** | Runs the DEOC during an event | Issue an alert, see who got it, know who didn't |
| **P2 — State Admin** | State DMA | Oversight across districts, historical performance |
| **P3 — Citizen** | Person in a hazard zone | Receive a warning, in my language, even with bad network — **[v3.0] and be able to answer back when I am not safe** |
| **P4 — Auditor / RTI applicant** | Post-event inquiry | *"Did the warning arrive? Prove it."* |
| **[v3.0] P5 — Field Responder / Relay Node** | Panchayat secretary, ASHA worker, police beat constable, school head | *"Tell me which households the system could not reach, so I can go there — and let me confirm when I have."* |

**P4 is the persona nobody else builds for. P5 is the persona that makes P4's answer complete** — without a relay node, the audit ledger goes silent at exactly the moment a village loses connectivity, which is precisely the moment the record matters most.

## 2.2 Feature inventory — **42 features**

**[C]** = Core, must ship. **[S]** = Stretch, build in listed order, stop at freeze.
**[v3.0]** marks the 17 features added in this release. **Tier** column: `T1` = cheap, reuses existing data, build first · `T2` = real work, finishable · `T3` = descoped or deferred, see Part 35.

### Module A — Ingestion & Composition

| # | Feature | | Owner | Tier |
|---|---|---|---|---|
| A1 | USGS + GDACS auto-ingestion, zero-auth, confirmed live | **[C]** | D1 | — |
| A2 | Thunderstorm/convective nowcast — Open-Meteo CAPE+LI+CIN → classifier (Trap 8) | **[C]** | D4 | — |
| A3 | Manual alert composer — draw polygon, compose, pick severity | **[C]** | D1 | — |
| A4 | Exposure preview — population + building count inside polygon, pre-send | **[C]** | D1 | — |
| A5 | Cross-source deduplication (ML) | **[C]** | D4 | — |
| A6 | Alert template library from historical events | [S] | D1 | — |
| A7 | SACHET + IMD parallel integration — strict upgrade, never blocking | [S] | D1 | — |

*No new features. The gaps v3.0 closes are all downstream of "an alert exists."*

### Module B — Delivery, Acknowledgement & Assurance Engine

| # | Feature | | Owner | Tier |
|---|---|---|---|---|
| B1 | Multi-channel fan-out (push, email, SMS, IVR, siren) via adapter registry | **[C]** | D2 | — |
| B2 | Per-recipient acknowledgement state machine | **[C]** | D2 | — |
| B3 | Policy-driven retry + channel escalation (zero hardcoded timings) | **[C]** | D2 | — |
| B4 | Immutable, hash-chained audit ledger | **[C]** | D2 | — |
| B5 | Reach-failure prediction (ML) driving pre-emptive escalation | **[C]** | D3 | — |
| B6 | IVR voice call with speech/DTMF acknowledgement | [S]→**[C]** | D2 | — |
| B7 | Siren/PA trigger adapter (webhook; simulated in demo) | [S] | D2 | — |
| **B8** | **[v3.0] Delivery Assurance Ladder** — six evidence levels, capability-table-driven, `not_applicable` where a channel genuinely cannot prove a tier (Rule 8) | **[C]** | D2 | **T1** |
| **B9** | **[v3.0] Trusted Human Relay Network** — registered relay nodes, IVR-confirmed physical dissemination, stored strictly separately from digital evidence (Rule 9) | **[C]** | D2 | **T2** |
| **B10** | **[v3.0] Community Relay Mode** — one-tap, citizen-initiated, Ed25519-verified peer alert transfer over Web Bluetooth to a nearby offline device (Rule 11, Trap 12) | **[C-demo]** | D5 | **T2** |

**B6 is promoted from [S] to [C] in v3.0.** It was a stretch item in v2.1; three new core features depend on it (B8's strongest device-delivered signal, B9's relay confirmation, C6's voice path for low-literacy citizens). A dependency of three core features cannot itself be stretch.

### Module C — Citizen PWA

| # | Feature | | Owner | Tier |
|---|---|---|---|---|
| C1 | Offline-first PWA (Service Worker + IndexedDB) | **[C]** | D5 | — |
| C2 | One-tap acknowledgement with offline queue + sync | **[C]** | D5 | — |
| C3 | Auto-translation to citizen's language (IndicTrans2 200M) | **[C]** | D4 | — |
| C4 | Nearest safe zone + evacuation route (OSM Overpass, Trap 9) | **[C]** | D5 | — |
| C5 | Citizen ground-report with NLP entity extraction | [S] | D4 | — |
| **C6** | **[v3.0] Structured Emergency Response** — I'M SAFE / NEED HELP → Trapped · Medical · Cannot evacuate · Other, with consent-gated location | **[C]** | D5 | **T1** |

**C6 supersedes C2's UI** (one binary tap) while reusing C2's entire offline-queue-and-sync mechanism and its idempotency contract. C2 is not deleted — it is the transport C6 rides on.

### Module D — Operations Console & Accountability

| # | Feature | | Owner | Tier |
|---|---|---|---|---|
| D1f | Live delivery map — status by unit, real-time via WebSocket | **[C]** | D3 | — |
| D2f | Real-time status table (sortable, filterable, virtualized) | **[C]** | D3 | — |
| D3f | Post-event audit report generator (PDF + CSV) | **[C]** | D6 | — |
| D4f | Historical performance analytics by district/channel | **[C]** | D6 | — |
| D5f | Disaster Copilot — RAG over SOPs/EAPs with citations | [S] | D4 | — |
| D6f | Public transparency page (aggregate, anonymised) | [S] | D6 | — |
| **D7f** | **[v3.0] Reachability Score** — per-unit reach against **estimated population** *and* registered recipients, side by side | **[C]** | D3 | **T1** |
| **D8f** | **[v3.0] Communication Vulnerability Map** — persistent structural dead-zone layer with config-driven recommended fallback | **[C]** | D3 | **T1** |
| **D9f** | **[v3.0] Incident Command Board** — one-screen common operating picture; built last, shows only real numbers | **[C]** | D3 | **T2** |
| **D10f** | **[v3.0] Incident Timeline** — chronological operational record, a view over the existing ledger | **[C]** | D3 | **T1** |
| **D11f** | **[v3.0] Assistance Priority Queue** — citizen responses → config-weighted, factor-explained, assignable cases | **[C]** | D3 | **T2** |
| **D12f** | **[v3.0] Decision Explanation** — "why was this unit flagged," surfacing already-stored features | **[C]** | D4 | **T1** |
| **D13f** | **[v3.0] Warning Lead-Time Analytics** — real for forecast hazards, `not_applicable` for earthquakes, publishes its own coverage | **[C]** | D6 | **T1** |
| **D14f** | **[v3.0] After-Action Intelligence** — measurement-cited recommendations; depends on D7f/D8f/D11f having real data | [S] | D6 | **T2** |

### Module E — Platform

| # | Feature | | Owner | Tier |
|---|---|---|---|---|
| E1 | RBAC auth (citizen / officer / state admin / auditor / **[v3.0] relay_node**) | **[C]** | D6 | — |
| E2 | Config-driven everything (policies, channels, thresholds in DB) | **[C]** | D6 | — |
| E3 | Public integration API + OpenAPI docs | [S] | D6 | — |
| **E4** | **[v3.0] Citizen Enrollment** — officer CSV bulk-import (dry-run + idempotent) and inbound-SMS keyword self-registration with STOP opt-out | **[C]** | D6 | **T2** |

### **[v3.0] Module F — Alert Lifecycle & Governance** *(new module — no equivalent existed in v2.1)*

| # | Feature | | Owner | Tier |
|---|---|---|---|---|
| **F1** | **Alert Readiness / Quality Gate** — six independently-testable pre-dispatch rules, thresholds in config, blocks dispatch with a named reason | **[C]** | D1 | **T1** |
| **F2** | **Incident & Alert Versioning** — scoped: columns on the existing `alert` table, `supersedes_alert_id` chain, in-flight cancellation of superseded retries | **[C]** | D1 | **T2** |
| **F3** | **Dual Authorization (Four-Eyes)** — two distinct human approvals for officer-composed severe/extreme; `authoritative_source` provenance for machine-ingested (Rule 12) | **[C]** | D6 | **T2** |
| **F4** | **Alert Fatigue Detection** — relabels a repeated related alert, **never suppresses** one | [S] | D2 | **T2** |

### The count, stated honestly

| | v2.1 | v3.0 |
|---|---|---|
| Core | 16 | **28** |
| Stretch | 9 | **14** |
| **Total** | **25** | **42** |

**Twenty-eight core features for six people is not a claim of comfort — it is only survivable because of the tier split.** Eight of the 14 new features (`T1`) are views, queries, or UI surfaces over data the platform already collects; they carry hours of work, not days. The six `T2` features are the real budget. Part 16 schedules them explicitly, and Part 35 records the seven capabilities we **rejected** so the count above is a list of things that will exist, not a wishlist.

---

# PART 3 — SYSTEM ARCHITECTURE

## 3.1 Service topology **[v3.0 — governance and response paths added]**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SOURCES                                │
│  USGS (quake)   GDACS (cyclone/flood/fire)   Open-Meteo→nowcast          │
│  Manual (officer)        [parallel/stretch: SACHET · IMD]                │
└───────────┬────────────────┬────────────────┬──────────┬─────────────────┘
            ▼                ▼                ▼          ▼
      ┌─────────────────────────────────────────────────┐
      │  INGESTION WORKER  (APScheduler, adapter-based) │
      │  · poll/ETag conditional GET · CAP/JSON parser  │
      │  · malformed alert → quarantine, log            │
      └──────────────────────┬──────────────────────────┘
                             ▼
      ┌─────────────────────────────────────────────────┐
      │  NORMALISATION + DEDUP                          │
      │  · CAP → canonical Alert  · embedding + cluster  │
      │  · [v3.0] attach to INCIDENT, assign version #  │
      └──────────────────────┬──────────────────────────┘
                             ▼
      ┌─────────────────────────────────────────────────┐
      │  TARGETING ENGINE            (PostGIS)          │
      │  ST_Intersects(polygon, admin_unit.geom)        │
      │  + exposure: WorldPop, OpenBuildings            │
      │  + reach-risk score per unit  (ML)              │
      └──────────────────────┬──────────────────────────┘
                             ▼
   ╔═════════════════════════════════════════════════════╗
   ║  [v3.0] GOVERNANCE GATE   (Module F)                ║
   ║  F1 quality gate → 6 rules, blocks on fail          ║
   ║  F3 authorization → N human approvals, OR            ║
   ║      approval_provenance='authoritative_source'      ║
   ║  ── nothing dispatches until both clear ──           ║
   ╚═════════════════════════┬═══════════════════════════╝
                             ▼
      ┌─────────────────────────────────────────────────┐
      │  DELIVERY ENGINE       (Redis Streams)          │
      │  batch XADD → consumer group → channel adapters │
      │  state machine per recipient (Postgres)         │
      │  retry ZSET · escalation policy from DB         │
      │  [v3.0] F4 fatigue relabel at message build     │
      └───────┬─────────────────────────────┬───────────┘
              ▼                             ▼
   ┌──────────────────────┐      ┌─────────────────────────┐
   │ CHANNEL ADAPTERS     │      │  AUDIT LEDGER           │
   │ FCM · Email · SMS    │─────▶│  hash-chained, append-  │
   │ IVR · Siren · Sim    │      │  only, PG-trigger-      │
   │ [v3.0] HumanRelay    │      │  enforced               │
   └───────┬──────────────┘      └───────────┬─────────────┘
           │                                  │
           │  [v3.0] every attempt also emits │
           ▼  a delivery_event (B8 ladder)    │
   ┌──────────────────────┐                   │
   │  CITIZEN PWA         │                   │
   │  offline-first       │                   │
   │  [v3.0] C6 structured│                   │
   │    response          │                   │
   │  [v3.0] B10 ⇄ BLE    │                   │
   │    peer relay        │                   │
   └───────┬──────────────┘                   │
           │ safe / need_help                 │
           ▼                                  ▼
   ┌──────────────────────┐      ┌─────────────────────────┐
   │ [v3.0] ASSISTANCE    │      │  OPS CONSOLE            │
   │ QUEUE (D11f)         │◀─WS─▶│  live map + table       │
   │ config-weighted,     │      │  [v3.0] D9f command     │
   │ factor-explained,    │      │    board                │
   │ assignable to teams  │      │  [v3.0] D10f timeline   │
   └──────────────────────┘      └─────────────────────────┘
```

**The one architectural claim worth defending in Q&A:** the governance gate (Module F) is the only genuinely *new* stage in the pipeline. Every other v3.0 feature is either (a) an additional writer into the existing audit/event tables, (b) an additional reader/view over existing tables, or (c) an additional adapter behind the existing channel Protocol. **That is why 17 features can land in 7 build days without a rewrite** — and it is the direct payoff of v2.0's Rule 2 (everything behind an interface) and Rule 1 (everything in config) having been enforced from Day 0 rather than retrofitted.

## 3.2 Repository layout **[v3.0 additions marked]**

```
setu/
├── services/
│   ├── ingestion/        adapters/{usgs,gdacs,thunderstorm,sachet,imd,manual}.py
│   │                     cap_parser.py  scheduler.py
│   │                     incident_linker.py                       ← [v3.0] F2
│   ├── targeting/        geo.py  exposure.py  reach_risk.py
│   ├── governance/                                                ← [v3.0] Module F
│   │                     quality_gate.py   rules/*.py             ← F1, one file per rule
│   │                     approvals.py                             ← F3
│   │                     versioning.py                            ← F2 supersede logic
│   ├── delivery/         engine.py  state_machine.py  retry.py
│   │                     assurance.py                             ← [v3.0] B8 event writer
│   │                     fatigue.py                               ← [v3.0] F4
│   │                     channels/{base,fcm,email,sms,ivr,siren,simulated}.py
│   │                     channels/human_relay.py                  ← [v3.0] B9
│   ├── response/                                                  ← [v3.0] C6 + D11f server side
│   │                     citizen_response.py  assistance_queue.py  priority.py
│   ├── enrollment/                                                ← [v3.0] E4
│   │                     csv_import.py  sms_keyword.py  phone_hash.py
│   ├── ml/               dedup/  reach_failure/  translate/  copilot/
│   ├── audit/            ledger.py  report.py
│   │                     timeline.py                              ← [v3.0] D10f
│   │                     after_action.py                          ← [v3.0] D14f
│   ├── crypto/           alert_signing.py                         ← [v3.0] B10 Ed25519 (Rule 11)
│   └── api/              main.py  routers/  deps.py  schemas/
├── web/
│   ├── console/          React ops console (dark-first)
│   │     src/pages/      LiveOps · Composer · AlertDetail · Analytics · Methodology
│   │                     IncidentPage.tsx                         ← [v3.0] F2
│   │                     CommandBoard.tsx                         ← [v3.0] D9f
│   │                     AssistanceQueue.tsx                      ← [v3.0] D11f
│   │                     ApprovalPanel.tsx                        ← [v3.0] F3
│   │     src/components/ AssuranceLadder.tsx                      ← [v3.0] B8, Rule 8 renderer
│   │                     ReachabilityCard.tsx                     ← [v3.0] D7f
│   └── citizen/          React PWA (light-first, offline)
│         src/            response.tsx                             ← [v3.0] C6
│                         relay.ts  verify.ts                      ← [v3.0] B10 + Rule 11
├── packages/tokens/      design tokens — single source for both apps
├── data/
│   ├── seeds/            admin units, channels, policies, app_config
│   │                     channel_capability.sql                   ← [v3.0] Rule 8 source of truth
│   │                     relay_nodes.sql                           ← [v3.0] B9
│   └── snapshots/        frozen demo fixtures (committed)
├── migrations/           alembic  (v3.0 chain: 0007→0012, Part 5.9)
├── tests/                unit/  property/  contract/  integration/  e2e/  fixtures/
├── scripts/              check_no_hardcoding.py  check_env_example.py
│                         check_channel_capability.py              ← [v3.0] Rule 8 CI gate
├── infra/                docker-compose.yml  render.yaml  vercel.json
└── .github/workflows/    ci.yml  deploy.yml  keepalive.yml  snapshot.yml  freeze-guard.yml
```

**Dependency direction is unchanged and still one-way.** `governance/` imports from `targeting/` and `delivery/` schemas but **nothing in `delivery/` imports `governance/`** — the gate is called by the API layer before dispatch, not from inside the engine. This keeps the delivery engine's 95%-branch-coverage test suite (Part 13) independent of the new layer, which is the difference between adding features and destabilising the one module that must not break.
---

# PART 4 — DATA LAYER

## 4.1 The geometry decision (and how we defend it)

| Level | Units | Simplified size | Fits Neon free? | Use |
|---|---|---|---|---|
| ADM2 District | 736 | 7.6 MB | ✅ easily | Fallback |
| **ADM3 Sub-district** | **6,836** | **38 MB** | ✅ **yes** | **Nationwide default** |
| ADM4 CD Block | 7,152 | 39 MB | ✅ yes | Alternative |
| ADM5 Village | 649,771 | 445 MB | ❌ **no** | **Demo slice: 1–2 states** |

Store simplified geometry with `ST_SimplifyPreserveTopology`, tolerance from config. Load ADM3 nationwide + ADM5 filtered to Kerala + Maharashtra (Wayanad and Palghar).

**The honest pitch line:** *"We target at sub-district resolution nationwide and village resolution in our two case-study states. Village-level nationwide is 1 GB of geometry — a hosting cost, not a technical barrier."*

**[v3.0] One consequence worth stating before a judge finds it:** D7f's Reachability Score divides by `admin_unit.population`. At ADM3 resolution nationwide, that denominator is a **sub-district** population (tens of thousands), so a nationwide reachability figure will look low and *should* — it is honest about how few citizens are enrolled. In the two ADM5 case-study states the denominator is a village population, which is the number that actually means something operationally. **The Command Board therefore labels every reachability figure with its geometry level** (`ADM3` / `ADM5`), because a 3% sub-district figure and a 3% village figure are different claims. Rule 4, applied to a derived metric.

## 4.2 Ingestion adapter contract

```python
# services/ingestion/adapters/base.py
from typing import Protocol, AsyncIterator
from datetime import datetime

class AlertSourceAdapter(Protocol):
    source_id: str
    is_authoritative: bool          # [v3.0] drives Rule 12 approval provenance

    async def discover(self, since: datetime) -> AsyncIterator[str]:
        """Yield alert identifiers newer than `since`."""
        ...

    async def fetch(self, identifier: str, etag: str | None) -> "RawAlert | NotModified":
        """Fetch one alert. Honour ETag; return NotModified on 304."""
        ...
```

Adapters are **registered from a DB table**, never imported by name in the engine:

```python
async def load_adapters(db) -> dict[str, AlertSourceAdapter]:
    registry = {}
    for row in await db.fetch("SELECT source_id, class_path, config FROM alert_source WHERE enabled"):
        cls = import_string(row["class_path"])
        registry[row["source_id"]] = cls(**row["config"])
    return registry
```

Adding IMD, or a new state's feed, is **one INSERT**. **[v3.0]** `alert_source.is_authoritative BOOLEAN` is the new column that Rule 12 reads: USGS and GDACS are `true` (a government seismograph network and a UN/EC-backed multi-hazard system are authorities in their own right); `manual` is `false` (a human composed it, so a second human must approve it); `thunderstorm_nowcast` is **`false`** — it is *our own derived model*, not an external authority, and Part 9.5 already labels it a bootstrap classifier. **Our own model does not get to authorize its own extreme alerts.** That decision is worth saying out loud in Q&A; it is the difference between a governance layer and a rubber stamp.

## 4.3 SACHET adapter — stretch-track, built against what is actually documented

Real code that ships, but in the [S] track (A7), registered via the same `alert_source` table. Discovery endpoint is `[UNVERIFIED]` and configured, not hardcoded, so it can be swapped the moment Day-1 DevTools work identifies the real one.

```python
class SachetAdapter:
    source_id = "sachet"
    is_authoritative = True                      # [v3.0] NDMA is an authority if it ever connects

    def __init__(self, base_url: str, discovery_url: str, timeout_s: int):
        self._base, self._discovery, self._timeout = base_url, discovery_url, timeout_s

    async def discover(self, since):
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._discovery)
            r.raise_for_status()
            for ident in parse_identifiers(r.content):   # tolerant of RSS *or* JSON
                yield ident

    async def fetch(self, identifier, etag):
        headers = {"If-None-Match": etag} if etag else {}
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(f"{self._base}/FetchXMLFile",
                            params={"identifier": identifier}, headers=headers)
        if r.status_code == 304:
            return NotModified()
        r.raise_for_status()
        return RawAlert(body=r.content, etag=r.headers.get("ETag"),
                        fetched_at=utcnow(), checksum=sha256(r.content).hexdigest())
```

## 4.4 CAP parsing must be defensive

36 state authorities implement CAP 1.2 independently. Expect missing fields, circles instead of polygons, absent geocodes, inconsistent encodings.

```python
def parse_cap(raw: bytes) -> ParsedAlert:
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError as e:
        raise QuarantineAlert(reason="malformed_xml", detail=str(e))

    info = first(root, "info") or raise_quarantine("missing_info")
    area = first(info, "area")

    geom = None
    if (poly := text(area, "polygon")):   geom = polygon_from_cap(poly)
    elif (circ := text(area, "circle")):  geom = circle_to_polygon(circ)
    elif (codes := texts(area, "geocode/value")):
        geom = await resolve_geocodes_to_geometry(codes)            # LGD code join
    else:
        raise QuarantineAlert(reason="no_geometry")
    ...
```

**A malformed alert is quarantined and logged, never crashes the poller.** The quarantine queue is visible in the console — that itself is a feature, because it surfaces which state feeds are broken.

## 4.5 The primary adapters — USGS, GDACS, Open-Meteo nowcast

```python
class UsgsAdapter:
    source_id = "usgs"
    is_authoritative = True                       # [v3.0]
    async def discover(self, since):
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._feed_url, params=self._india_bbox_params(since))
            r.raise_for_status()
            for feat in r.json()["features"]:
                yield feat["id"]                  # zero auth, confirmed live

class GdacsAdapter:
    source_id = "gdacs"
    is_authoritative = True                       # [v3.0]
    async def discover(self, since): ...

class ThunderstormNowcastAdapter:
    """Not a feed — a derived signal. Polls Open-Meteo per admin-unit centroid,
       thresholds CAPE / Lifted Index / CIN / precip probability (all from config),
       and synthesises a CAP-shaped alert when risk crosses the configured floor."""
    source_id = "thunderstorm_nowcast"
    is_authoritative = False                      # [v3.0] our own model — needs human approval
    async def discover(self, since):
        feats = await open_meteo.fetch_hourly(self._unit_centroids,
                    vars=["cape", "lifted_index", "cin", "precipitation_probability"])
        for unit_id, row in feats.items():
            if self._classifier.risk(row) >= self._cfg.alert_floor:
                yield synth_identifier(unit_id, row.time)
```

**[v3.0] Estimated onset time, for D13f.** Each adapter now also populates `alert.estimated_onset_at` where the source genuinely provides one, and leaves it `NULL` where it does not:

| Source | `estimated_onset_at` | Why |
|---|---|---|
| GDACS (cyclone/flood) | ✅ from the event's forecast window | Forecast hazards have a projected arrival |
| Open-Meteo nowcast | ✅ the hour the risk score crosses the floor | The convective window is the forecast |
| Manual (officer) | ✅ **optional field in the composer** | The officer usually knows; if unknown, left NULL, never guessed |
| **USGS earthquake** | ❌ **always NULL** | A quake is detected *after* it happens. There is no lead time to measure, and inventing one would be the single most obviously fake number in the product. |

D13f's view therefore reports lead-time metrics **and its own coverage percentage** ("lead time computed for 61% of alerts; the remainder are seismic events, which have no forecast onset"). Publishing the coverage alongside the metric is Rule 6 applied to a metric that is legitimately partial.

## 4.6 Safe-zone / evacuation-route data (Trap 9)

```
[out:json][timeout:25];
area["ISO3166-1"="IN"]->.india;
(
  node["amenity"~"school|community_centre|hospital"](area.india);
  node["emergency"="shelter"](area.india);
  node["building"="government"]["amenity"="townhall"](area.india);
);
out center;
```
Free, no auth, FOSSGIS main instance — safe under 10K queries/day. Add a distinct User-Agent (their documented courtesy requirement). Results seeded into `safe_zone` at build time with a nightly refresh, not queried live per request. Routing is straight-line-to-nearest for the demo (haversine + `ST_Distance`); turn-by-turn is explicitly cuttable.

**[v3.0] One cheap, real upgrade that needs no new data source:** reject a safe-zone recommendation whose straight line to the citizen **crosses the alert polygon**, and fall through to the next-nearest. This is `ST_Intersects(ST_MakeLine(citizen_pt, zone_pt), alert.area)` — pure PostGIS over geometry we already hold. It is *not* the full risk-aware routing of Part 35's deferred list (which needs live road closures that do not exist for free in India), and the UI says so: *"Route avoids the warning area. Road conditions are not included — we have no live source for them."*

## 4.7 **[v3.0] Relay node registry (B9)**

`relay_node` is **seeded data, not code** (Rule 3), from `data/seeds/relay_nodes.sql`. For the demo we seed **six real, publicly-listed institution types** across the two case-study districts — a panchayat office, a police station, a government school, a PHC, and two ASHA/volunteer entries — with **team members' own verified phone numbers as the contact**, because a Twilio trial can only call verified numbers (Trap 5) and because cold-calling a real panchayat office during a hackathon demo would be indefensible.

**Said explicitly in the pitch:** *"The relay nodes in this demo are real institution types with our own phones behind them. In deployment the phone number is the panchayat secretary's, and the workflow is identical — this is the same boundary we drew for SMS."*

```sql
-- data/seeds/relay_nodes.sql
INSERT INTO relay_node (unit_id, kind, name, phone_hash, phone_enc, active) VALUES
  (:wayanad_unit, 'panchayat',     'Meppadi Panchayat Office (demo contact)',  :h1, :e1, true),
  (:wayanad_unit, 'police',        'Meppadi Police Station (demo contact)',    :h2, :e2, true),
  (:wayanad_unit, 'health_worker', 'ASHA — Meppadi Ward 4 (demo contact)',     :h3, :e3, true),
  (:palghar_unit, 'panchayat',     'Talasari Panchayat Office (demo contact)', :h4, :e4, true),
  (:palghar_unit, 'school',        'ZP School Talasari (demo contact)',        :h5, :e5, true),
  (:palghar_unit, 'volunteer',     'Registered volunteer — Talasari (demo)',   :h6, :e6, true);
```

**Coverage rule, in config not code:** a relay node covers its own `unit_id`. If a unit has no active relay node, B9's adapter raises `ChannelUnavailable("no_relay_node_registered_for_unit")` and the Command Board shows that unit as **"unreachable — no relay coverage"**, which is itself one of the most useful preparedness outputs in the product: *it names the villages where the last resort does not exist yet.*

---

# PART 5 — DATABASE SCHEMA

Full DDL. Note how much of it is **configuration**, not code. **[v3.0] additions are grouped and marked; nothing from v2.1 was altered except the two `ALTER TABLE`s in §5.5 and §5.8, both called out explicitly.**

## 5.1 Geography (v2.1, unchanged)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE admin_unit (
    id            BIGSERIAL PRIMARY KEY,
    lgd_code      BIGINT UNIQUE,
    level         SMALLINT NOT NULL,                -- 2=district 3=subdistrict 5=village
    name          TEXT NOT NULL,
    parent_id     BIGINT REFERENCES admin_unit(id),
    geom          GEOMETRY(MultiPolygon, 4326) NOT NULL,
    centroid      GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS
                    (ST_Centroid(geom)::geography) STORED,
    population    INTEGER,                          -- WorldPop
    building_count INTEGER,                         -- Google Open Buildings
    source_id     TEXT NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX admin_unit_geom_gix ON admin_unit USING GIST (geom);
CREATE INDEX admin_unit_level_ix ON admin_unit (level);

CREATE TABLE unit_features (
    unit_id            BIGINT PRIMARY KEY REFERENCES admin_unit(id),
    terrain_ruggedness NUMERIC,     -- Copernicus GLO-30, SRTM fallback
    tower_count_5km    INTEGER,     -- OpenCelliD
    nearest_tower_km   NUMERIC,
    mean_elevation_m   NUMERIC,
    computed_at        TIMESTAMPTZ NOT NULL,
    feature_version    TEXT NOT NULL
);

CREATE TABLE safe_zone (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT,
    kind        TEXT NOT NULL,     -- shelter|school|hospital|community_centre|townhall
    geom        GEOGRAPHY(Point, 4326) NOT NULL,
    unit_id     BIGINT REFERENCES admin_unit(id),
    source_id   TEXT NOT NULL DEFAULT 'osm_overpass',
    fetched_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX safe_zone_geom_gix ON safe_zone USING GIST (geom);
```

## 5.2 Configuration (v2.1 + v3.0 capability table)

```sql
CREATE TABLE app_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    unit  TEXT,
    note  TEXT
);

CREATE TABLE alert_source (
    source_id       TEXT PRIMARY KEY,
    class_path      TEXT NOT NULL,
    config          JSONB NOT NULL,
    poll_interval_s INTEGER NOT NULL,
    is_authoritative BOOLEAN NOT NULL DEFAULT false,   -- [v3.0] Rule 12
    enabled         BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE channel (
    id          SMALLSERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,     -- fcm|email|sms|ivr|siren|sim|human_relay|community_relay
    class_path  TEXT NOT NULL,
    config      JSONB NOT NULL,
    cost_weight NUMERIC NOT NULL DEFAULT 0,
    enabled     BOOLEAN NOT NULL DEFAULT true
);

-- ═══ [v3.0] THE RULE 8 SOURCE OF TRUTH ═══
-- Which assurance tiers each channel can PROVE. Read by the API and the UI.
-- Never a hardcoded map in TypeScript. Never inferred at render time.
CREATE TABLE channel_capability (
    channel_id                SMALLINT PRIMARY KEY REFERENCES channel(id),
    supports_provider_accept  BOOLEAN NOT NULL,
    supports_device_delivered BOOLEAN NOT NULL,
    supports_opened           BOOLEAN NOT NULL,
    supports_acknowledgement  BOOLEAN NOT NULL,
    device_delivered_source   TEXT,     -- how it is proven, shown in the methodology page
    not_applicable_reason     TEXT      -- rendered verbatim in the UI where a tier is false
);

CREATE TABLE escalation_policy (
    id                   SMALLSERIAL PRIMARY KEY,
    severity             TEXT NOT NULL,
    step_order           SMALLINT NOT NULL,
    channel_id           SMALLINT NOT NULL REFERENCES channel(id),
    wait_before_next_s   INTEGER NOT NULL,
    backoff_multiplier   NUMERIC NOT NULL DEFAULT 1.0,
    jitter_ms            INTEGER NOT NULL DEFAULT 0,
    max_wait_s           INTEGER,
    max_attempts         SMALLINT NOT NULL,
    applies_if_reach_risk_gte NUMERIC,
    UNIQUE (severity, step_order)
);
```

## 5.3 **[v3.0] Incidents & alert lifecycle (F2)**

```sql
CREATE TABLE incident (
    id             BIGSERIAL PRIMARY KEY,
    label          TEXT NOT NULL,          -- 'WAYANAD-FLOOD-001', generated, not typed
    incident_type  TEXT NOT NULL,          -- flood|cyclone|earthquake|thunderstorm|other
    status         TEXT NOT NULL DEFAULT 'active',   -- active|closed
    origin_source  TEXT NOT NULL REFERENCES alert_source(source_id),
    opened_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at      TIMESTAMPTZ,
    CHECK (status <> 'closed' OR closed_at IS NOT NULL)   -- can't close without a time
);
CREATE INDEX incident_status_ix ON incident (status);
```

## 5.4 Alerts (v2.1 + v3.0 lifecycle columns)

```sql
CREATE TABLE alert (
    id            BIGSERIAL PRIMARY KEY,
    external_id   TEXT,
    source_id     TEXT NOT NULL REFERENCES alert_source(source_id),
    cluster_id    BIGINT,
    severity      TEXT NOT NULL,
    headline      TEXT NOT NULL,
    body          TEXT NOT NULL,
    lang          TEXT NOT NULL,
    area          GEOMETRY(MultiPolygon, 4326) NOT NULL,
    effective_at  TIMESTAMPTZ NOT NULL,
    expires_at    TIMESTAMPTZ,
    raw_checksum  TEXT NOT NULL,
    etag          TEXT,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- ═══ [v3.0] lifecycle: columns on the EXISTING table, not a new entity (scoped, Part 35) ═══
    incident_id         BIGINT REFERENCES incident(id),
    version_number      SMALLINT NOT NULL DEFAULT 1,
    supersedes_alert_id BIGINT REFERENCES alert(id),
    change_reason       TEXT,                      -- required when version_number > 1
    lifecycle_status    TEXT NOT NULL DEFAULT 'draft',
                        -- draft|pending_approval|active|superseded|cancelled|resolved
    estimated_onset_at  TIMESTAMPTZ,               -- [v3.0] D13f; NULL for seismic (§4.5)
    signature           BYTEA,                     -- [v3.0] Ed25519 over canonical core fields (Rule 11)
    UNIQUE (source_id, external_id),
    CHECK (version_number = 1 OR change_reason IS NOT NULL),
    CHECK (version_number = 1 OR supersedes_alert_id IS NOT NULL)
);
CREATE INDEX alert_area_gix ON alert USING GIST (area);
CREATE INDEX alert_incident_ix ON alert (incident_id, version_number DESC);
CREATE INDEX alert_lifecycle_ix ON alert (lifecycle_status);

-- Exactly one active version per incident, enforced by the database, not by the app.
CREATE UNIQUE INDEX alert_one_active_per_incident_uix
  ON alert (incident_id) WHERE lifecycle_status = 'active';

CREATE TABLE alert_quarantine (
    id         BIGSERIAL PRIMARY KEY,
    source_id  TEXT NOT NULL,
    raw        BYTEA NOT NULL,
    reason     TEXT NOT NULL,
    detail     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alert_translation (
    alert_id  BIGINT NOT NULL REFERENCES alert(id),
    lang      TEXT NOT NULL,
    headline  TEXT NOT NULL,
    body      TEXT NOT NULL,
    model_id  SMALLINT REFERENCES model_registry(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (alert_id, lang)
);
```

**`alert_one_active_per_incident_uix` is the single most valuable line in this section.** It makes "two contradictory live versions of the same warning" a database error rather than an operational ambiguity — which is exactly the failure Gap A described. A partial unique index costs nothing and cannot be bypassed by a bug in application code.

## 5.5 **[v3.0] Governance: approvals & quality gate (F1, F3)**

```sql
CREATE TABLE app_user (              -- referenced by v2.1's RBAC, DDL made explicit here
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    role          TEXT NOT NULL,     -- citizen|officer|state_admin|auditor|relay_node
    unit_scope_id BIGINT REFERENCES admin_unit(id),
    active        BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE alert_approval (
    id           BIGSERIAL PRIMARY KEY,
    alert_id     BIGINT NOT NULL REFERENCES alert(id),
    approver_id  BIGINT REFERENCES app_user(id),      -- NULL only for machine provenance
    provenance   TEXT NOT NULL,      -- human|authoritative_source
    decision     TEXT NOT NULL,      -- approved|rejected
    reason       TEXT,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Rule 12: the same officer can never count twice toward a quorum.
    UNIQUE (alert_id, approver_id),
    CHECK ((provenance = 'human' AND approver_id IS NOT NULL)
        OR (provenance = 'authoritative_source' AND approver_id IS NULL)),
    CHECK (decision <> 'rejected' OR reason IS NOT NULL)   -- a rejection must say why
);
CREATE INDEX alert_approval_alert_ix ON alert_approval (alert_id, decision);

CREATE TABLE alert_validation_result (
    id         BIGSERIAL PRIMARY KEY,
    alert_id   BIGINT NOT NULL REFERENCES alert(id),
    rule_id    TEXT NOT NULL,
    status     TEXT NOT NULL,        -- pass|fail|warn
    message    TEXT,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX alert_validation_alert_ix ON alert_validation_result (alert_id, evaluated_at DESC);
```

`UNIQUE (alert_id, approver_id)` is what makes Four-Eyes real rather than theatrical: **the "second approval" cannot be the same person clicking twice**, and it is the database that refuses, not a UI check that a determined officer could bypass by replaying a request.

## 5.6 Recipients & delivery (v2.1 + v3.0 `phone_hash` from Trap 11)

```sql
CREATE TABLE recipient (
    id             BIGSERIAL PRIMARY KEY,
    unit_id        BIGINT NOT NULL REFERENCES admin_unit(id),
    kind           TEXT NOT NULL,          -- citizen|official|siren_node|relay_node
    push_token     TEXT,
    email_enc      BYTEA,
    phone_enc      BYTEA,                  -- recoverable, randomized, reveal path only
    phone_hash     BYTEA,                  -- [v3.0] HMAC+pepper, deterministic, dedupe key (Trap 11)
    preferred_lang TEXT NOT NULL DEFAULT 'en',
    consented_at   TIMESTAMPTZ,
    consent_source TEXT,                   -- [v3.0] csv_import|sms_keyword|pwa_signup
    opted_out_at   TIMESTAMPTZ,            -- [v3.0] STOP keyword, TRAI-aligned
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX recipient_unit_ix ON recipient (unit_id);
CREATE UNIQUE INDEX recipient_phone_hash_uix ON recipient (phone_hash) WHERE phone_hash IS NOT NULL;

CREATE TYPE delivery_state AS ENUM
  ('pending','queued','sent','delivered','acknowledged','failed','expired','escalated');

CREATE TABLE delivery (
    id            BIGSERIAL PRIMARY KEY,
    alert_id      BIGINT NOT NULL REFERENCES alert(id),
    recipient_id  BIGINT NOT NULL REFERENCES recipient(id),
    channel_id    SMALLINT NOT NULL REFERENCES channel(id),
    attempt       SMALLINT NOT NULL DEFAULT 1,
    state         delivery_state NOT NULL DEFAULT 'pending',
    provider_ref  TEXT,
    simulated     BOOLEAN NOT NULL DEFAULT false,
    queued_at     TIMESTAMPTZ,
    sent_at       TIMESTAMPTZ,
    delivered_at  TIMESTAMPTZ,
    acked_at      TIMESTAMPTZ,
    failed_reason TEXT,
    UNIQUE (alert_id, recipient_id, channel_id, attempt)
);
CREATE INDEX delivery_alert_state_ix ON delivery (alert_id, state);
CREATE INDEX delivery_provider_ref_ix ON delivery (provider_ref);   -- [v3.0] webhook lookups
```

## 5.7 **[v3.0] Delivery Assurance Ladder (B8)**

```sql
CREATE TYPE assurance_event AS ENUM (
    'delivery_attempted',      -- 0  we tried
    'provider_accepted',       -- 1  the provider took it
    'device_delivered',        -- 2  it reached a device / a human answered
    'notification_opened',     -- 3  it was opened
    'acknowledged',            -- 4  the citizen tapped/pressed
    'citizen_response'         -- 5  the citizen told us something (C6)
);

CREATE TABLE delivery_event (
    id          BIGSERIAL PRIMARY KEY,
    delivery_id BIGINT NOT NULL REFERENCES delivery(id),
    event_type  assurance_event NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source      TEXT NOT NULL,   -- server|fcm_send|client_sw|twilio_sms_webhook|
                                 -- twilio_call_webhook|ivr_dtmf|relay_ivr|peer_relay
    evidence_id TEXT,            -- provider message id / CallSid / SW nonce  (Rule 4)
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (delivery_id, event_type)   -- one row per tier per delivery; replays are idempotent
);
CREATE INDEX delivery_event_delivery_ix ON delivery_event (delivery_id);
CREATE INDEX delivery_event_type_ix ON delivery_event (event_type);

-- The ladder's numeric level, derived — never stored twice (single source of truth).
CREATE OR REPLACE FUNCTION assurance_level(p_delivery_id BIGINT) RETURNS SMALLINT AS $$
  SELECT COALESCE(MAX(CASE event_type
      WHEN 'delivery_attempted'   THEN 0
      WHEN 'provider_accepted'    THEN 1
      WHEN 'device_delivered'     THEN 2
      WHEN 'notification_opened'  THEN 3
      WHEN 'acknowledged'         THEN 4
      WHEN 'citizen_response'     THEN 5 END), -1)
  FROM delivery_event WHERE delivery_id = p_delivery_id;
$$ LANGUAGE sql STABLE;
```

**`UNIQUE (delivery_id, event_type)` is what makes provider webhooks safe.** Twilio retries status callbacks; a duplicate callback must not create a second `device_delivered` row and inflate the ladder. Insert with `ON CONFLICT DO NOTHING` and the retry becomes a no-op — the same idempotency discipline v2.1 already applied to `POST /ack`, now applied to every inbound provider signal.

**Why `assurance_level` is a function, not a column:** a stored column would need to be updated by every writer and could drift from its own event rows. Deriving it means the ladder is *always* exactly what the evidence says. Rule 4 is easier to keep when there is nothing to keep in sync.

## 5.8 **[v3.0] Citizen response & assistance (C6, D11f)**

```sql
CREATE TABLE citizen_response (
    id               BIGSERIAL PRIMARY KEY,
    delivery_id      BIGINT NOT NULL REFERENCES delivery(id),
    alert_id         BIGINT NOT NULL REFERENCES alert(id),      -- denormalised for query speed
    unit_id          BIGINT NOT NULL REFERENCES admin_unit(id),
    response_type    TEXT NOT NULL,   -- safe|trapped|medical|unable_to_evacuate|other
    free_text        TEXT,            -- only for 'other'; length-capped in the API schema
    location         GEOGRAPHY(Point, 4326),
    location_consent BOOLEAN NOT NULL DEFAULT false,
    idempotency_key  TEXT NOT NULL,
    submitted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),        -- differs when queued offline
    UNIQUE (idempotency_key),
    -- A location may only be stored if consent was actually given. Enforced, not trusted.
    CHECK (location IS NULL OR location_consent = true)
);
CREATE INDEX citizen_response_alert_ix ON citizen_response (alert_id, response_type);
CREATE INDEX citizen_response_geom_gix ON citizen_response USING GIST (location);

CREATE TABLE assistance_case (
    id                  BIGSERIAL PRIMARY KEY,
    citizen_response_id BIGINT NOT NULL UNIQUE REFERENCES citizen_response(id),
    priority_score      NUMERIC NOT NULL CHECK (priority_score BETWEEN 0 AND 1),
    priority_factors    JSONB NOT NULL,        -- Rule 10: NOT NULL, the score is never a black box
    model_version       TEXT NOT NULL,         -- which weight-set produced it
    status              TEXT NOT NULL DEFAULT 'new',
                        -- new|assigned|en_route|assisted|closed
    assigned_team       TEXT,
    assigned_by         BIGINT REFERENCES app_user(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ,
    CHECK (status = 'new' OR assigned_team IS NOT NULL),
    CHECK (status <> 'closed' OR resolved_at IS NOT NULL)
);
CREATE INDEX assistance_status_priority_ix ON assistance_case (status, priority_score DESC);
```

`CHECK (location IS NULL OR location_consent = true)` is Part 12's privacy promise expressed as a constraint. A future bug that forgets to check consent in application code **cannot** write a location — the insert fails. This is the same philosophy as the `audit_immutable` trigger: the rule you care about most belongs in the database.

## 5.9 **[v3.0] Human relay (B9)**

```sql
CREATE TABLE relay_node (
    id          BIGSERIAL PRIMARY KEY,
    unit_id     BIGINT NOT NULL REFERENCES admin_unit(id),
    kind        TEXT NOT NULL,   -- panchayat|police|school|health_worker|volunteer|shelter
    name        TEXT NOT NULL,
    phone_enc   BYTEA NOT NULL,
    phone_hash  BYTEA NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT true,
    seeded_from TEXT NOT NULL DEFAULT 'data/seeds/relay_nodes.sql'   -- Rule 3 provenance
);
CREATE INDEX relay_node_unit_ix ON relay_node (unit_id) WHERE active;

CREATE TABLE relay_confirmation (
    id                 BIGSERIAL PRIMARY KEY,
    delivery_id        BIGINT NOT NULL REFERENCES delivery(id),
    relay_node_id      BIGINT NOT NULL REFERENCES relay_node(id),
    unit_id            BIGINT NOT NULL REFERENCES admin_unit(id),
    confirmed_by_human BOOLEAN NOT NULL DEFAULT true,   -- Rule 9: never mixed with digital
    method             TEXT NOT NULL,                   -- ivr_dtmf|console_checkin
    households_claimed INTEGER,                          -- optional, self-reported, labelled as such
    confirmed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (delivery_id, relay_node_id)
);
```

`households_claimed` is deliberately named **`_claimed`, not `_reached`.** It is a human's self-report over a phone keypad; the schema's column name is the first line of defence against a report later presenting it as verified fact. Rule 9 lives in naming as much as in structure.

## 5.10 Audit ledger (v2.1, unchanged — and it is what everything new writes into)

```sql
CREATE TABLE audit_event (
    id          BIGSERIAL PRIMARY KEY,
    alert_id    BIGINT REFERENCES alert(id),
    delivery_id BIGINT REFERENCES delivery(id),
    incident_id BIGINT REFERENCES incident(id),          -- [v3.0] for D10f timeline grouping
    event_type  TEXT NOT NULL,
    payload     JSONB NOT NULL,
    actor       TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_hash   TEXT NOT NULL,
    hash        TEXT NOT NULL          -- sha256(prev_hash || canonical_json(payload))
);
CREATE UNIQUE INDEX audit_hash_uix ON audit_event (hash);
CREATE INDEX audit_incident_ix ON audit_event (incident_id, occurred_at);   -- [v3.0]

CREATE OR REPLACE FUNCTION audit_no_mutate() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_event is append-only'; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_immutable
  BEFORE UPDATE OR DELETE ON audit_event
  FOR EACH ROW EXECUTE FUNCTION audit_no_mutate();
```

**[v3.0] Every new feature emits audit events**, so the ledger remains the single record of truth: `incident.opened`, `alert.version_created`, `alert.superseded`, `alert.validation_failed`, `alert.approved`, `alert.rejected`, `delivery.assurance_advanced`, `citizen.response_received`, `assistance.assigned`, `assistance.resolved`, `relay.confirmed`, `recipient.enrolled`, `recipient.opted_out`, `contact.revealed`. **There is no second log.** D10f's timeline is a `SELECT` over this table, which is why it costs hours rather than days.

## 5.11 ML registry (v2.1, unchanged)

```sql
CREATE TABLE model_registry (
    id           SMALLSERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    version      TEXT NOT NULL,
    artifact_uri TEXT NOT NULL,
    metrics      JSONB NOT NULL,
    is_bootstrap BOOLEAN NOT NULL,
    trained_at   TIMESTAMPTZ NOT NULL,
    active       BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (name, version)
);

CREATE TABLE reach_prediction (
    alert_id   BIGINT NOT NULL REFERENCES alert(id),
    unit_id    BIGINT NOT NULL REFERENCES admin_unit(id),
    risk_score NUMERIC NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
    model_id   SMALLINT NOT NULL REFERENCES model_registry(id),
    features   JSONB NOT NULL,          -- full explainability, D12f reads this
    PRIMARY KEY (alert_id, unit_id)
);
```

## 5.12 **[v3.0] Derived views — D7f, D8f, D13f**

Views, not tables. Nothing is duplicated, nothing can drift, and a view costs no migration risk.

```sql
-- ═══ D7f REACHABILITY SCORE ═══
-- Two denominators, side by side, deliberately. §4.1 explains why both are needed.
-- Tier floors come from app_config, not from literals in the view body. What counts as
-- "reached" is a POLICY decision (is provider-acceptance enough? we say no), and a policy
-- decision belongs in a config row where it can be read aloud in Q&A. Part 38, violation B.
CREATE VIEW v_reachability AS
WITH cfg AS (
  SELECT
    (SELECT value::int FROM app_config WHERE key='reachability.reached_tier_floor')     AS reached_floor,
    (SELECT value::int FROM app_config WHERE key='reachability.acknowledged_tier_floor') AS ack_floor
)
SELECT
    u.id                                   AS unit_id,
    u.name,
    u.level                                AS geometry_level,   -- labelled in the UI (§4.1)
    u.population                           AS estimated_population,
    COUNT(DISTINCT r.id)                   AS registered_recipients,
    COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.reached_floor)
                                           AS reached_recipients,
    COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.ack_floor)
                                           AS acknowledged_recipients,
    COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) <  cfg.reached_floor)
                                           AS unverified_recipients,
    ROUND(100.0 * COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.reached_floor)
          / NULLIF(COUNT(DISTINCT r.id), 0), 1)     AS recipient_reach_pct,
    ROUND(100.0 * COUNT(DISTINCT d.recipient_id) FILTER (WHERE assurance_level(d.id) >= cfg.reached_floor)
          / NULLIF(u.population, 0), 1)             AS population_reach_pct,
    MAX(d.queued_at)                       AS last_dispatch_at
FROM admin_unit u
LEFT JOIN recipient r ON r.unit_id = u.id AND r.opted_out_at IS NULL
LEFT JOIN delivery  d ON d.recipient_id = r.id
CROSS JOIN cfg
GROUP BY u.id, u.name, u.level, u.population, cfg.reached_floor, cfg.ack_floor;

-- ═══ D8f COMMUNICATION VULNERABILITY ═══
-- Thresholds from app_config, never literals. Degrades honestly if OpenCelliD slipped (Part 30).
CREATE VIEW v_communication_vulnerability AS
WITH cfg AS (
  SELECT
    (SELECT value::numeric FROM app_config WHERE key='vuln.tower_count_floor')      AS tower_floor,
    (SELECT value::numeric FROM app_config WHERE key='vuln.terrain_ruggedness_ceiling') AS terrain_ceil,
    (SELECT value::numeric FROM app_config WHERE key='vuln.historical_reach_floor_pct') AS reach_floor
)
SELECT
    u.id AS unit_id, u.name,
    uf.tower_count_5km, uf.nearest_tower_km, uf.terrain_ruggedness,
    rv.recipient_reach_pct AS historical_reach_pct,
    -- A unit is vulnerable on any of three independent grounds; we report WHICH.
    ARRAY_REMOVE(ARRAY[
      CASE WHEN uf.tower_count_5km IS NOT NULL AND uf.tower_count_5km < cfg.tower_floor
           THEN 'low_tower_density' END,
      CASE WHEN uf.terrain_ruggedness IS NOT NULL AND uf.terrain_ruggedness > cfg.terrain_ceil
           THEN 'terrain_obstruction' END,
      CASE WHEN rv.recipient_reach_pct IS NOT NULL AND rv.recipient_reach_pct < cfg.reach_floor
           THEN 'historical_delivery_failure' END,
      CASE WHEN NOT EXISTS (SELECT 1 FROM relay_node rn WHERE rn.unit_id = u.id AND rn.active)
           THEN 'no_relay_coverage' END           -- §4.7: names where the last resort is missing
    ], NULL) AS primary_factors,
    CASE
      WHEN uf.tower_count_5km IS NULL THEN 'unknown_connectivity_features_pending'
      WHEN uf.tower_count_5km < cfg.tower_floor AND uf.terrain_ruggedness > cfg.terrain_ceil
           THEN 'ivr_plus_field_relay'
      WHEN uf.tower_count_5km < cfg.tower_floor THEN 'sms_plus_ivr'
      ELSE 'standard'
    END AS recommended_fallback
FROM admin_unit u
JOIN unit_features uf ON uf.unit_id = u.id
LEFT JOIN v_reachability rv ON rv.unit_id = u.id
CROSS JOIN cfg;

-- ═══ D13f WARNING LEAD TIME ═══
-- Only where a forecast onset genuinely exists. Publishes its own coverage.
CREATE VIEW v_lead_time AS
SELECT
    a.id AS alert_id, a.incident_id, d.recipient_id,
    r.unit_id,
    EXTRACT(EPOCH FROM (a.estimated_onset_at - de.occurred_at))/60 AS lead_time_minutes
FROM alert a
JOIN delivery d ON d.alert_id = a.id
JOIN recipient r ON r.id = d.recipient_id
JOIN delivery_event de ON de.delivery_id = d.id AND de.event_type = 'device_delivered'
WHERE a.estimated_onset_at IS NOT NULL;      -- seismic alerts correctly excluded (§4.5)

CREATE VIEW v_lead_time_coverage AS
SELECT
    COUNT(*) FILTER (WHERE estimated_onset_at IS NOT NULL) AS alerts_with_onset,
    COUNT(*)                                               AS alerts_total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE estimated_onset_at IS NOT NULL)
          / NULLIF(COUNT(*), 0), 1)                        AS coverage_pct
FROM alert WHERE lifecycle_status IN ('active','superseded','resolved');
```

## 5.13 **[v3.0] Migration chain — explicit, ordered, reviewable**

Alembic revisions must be applied in this order; each is independently reversible, and each ships with the seed data it needs so no revision leaves the database in a state the application cannot read.

| Rev | Contents | Down-migration safe? |
|---|---|---|
| `0007_incident_lifecycle` | `incident`; `alert` lifecycle columns; `alert_one_active_per_incident_uix`; backfill: every existing alert gets its own single-version incident | ✅ drops columns, no data loss for v2.1 features |
| `0008_governance` | `app_user` (if not already present), `alert_approval`, `alert_validation_result` + `app_config` approval rows | ✅ |
| `0009_assurance` | `assurance_event` enum, `delivery_event`, `assurance_level()` function, `channel_capability` + its seed | ⚠️ dropping the enum requires dropping the table first — noted in the down-revision |
| `0010_citizen_response` | `citizen_response`, `assistance_case` + `app_config` weight rows | ✅ |
| `0011_relay` | `relay_node`, `relay_confirmation`, `human_relay` channel row + capability row + node seeds | ✅ |
| `0012_enrollment_and_views` | `recipient.phone_hash` + unique index + backfill, `consent_source`, `opted_out_at`; all three views | ⚠️ backfill needs `PHONE_HASH_PEPPER` present — migration **fails loudly** if the env var is missing rather than writing NULLs |

**`0012` failing loudly on a missing pepper is deliberate.** A migration that silently backfilled `phone_hash = NULL` would leave the unique index inert and re-introduce Trap 11 without a single error message.

---

# PART 6 — REDIS DESIGN

## 6.1 Key schema (namespaced, versioned, no literals in code)

```
setu:v1:stream:delivery                 Stream   — batched delivery jobs
setu:v1:group:workers                   Consumer group
setu:v1:zset:retry                      ZSET     — score = unix ts of next attempt
setu:v1:set:dedup:{yyyymmdd}            SET      — seen alert checksums, TTL 48h
setu:v1:geo:units                       GEO      — unit centroids for radius queries
setu:v1:chan:alert:{alert_id}           Pub/Sub  — throttled live updates
setu:v1:lock:ingest:{source_id}         String   — SET NX PX, prevents double-poll
setu:v1:zset:assistance                 ZSET     — [v3.0] open cases by priority, 1 ZADD per batch
setu:v1:lock:supersede:{incident_id}    String   — [v3.0] SET NX PX, serialises version transitions
```

All prefixes come from `settings.redis_namespace` — never typed inline.

**[v3.0] `lock:supersede:{incident_id}` closes a real race.** Two officers escalating the same incident simultaneously could both try to become `lifecycle_status='active'`. The partial unique index (§5.4) would make the second one *fail*, which is correct but produces an ugly 500. The lock makes the second officer get a clean 409 *"another version is being published for this incident, retry in a moment"* instead. Belt (index) and braces (lock) — the index is the guarantee, the lock is the user experience.

## 6.2 Batched fan-out (the command-budget fix)

```python
BATCH = settings.delivery_batch_size          # config, not a literal

async def enqueue_fanout(alert_id: int, recipient_ids: list[int]) -> None:
    """One XADD per batch of N recipients, not one per recipient."""
    for chunk in chunked(recipient_ids, BATCH):
        await redis.xadd(
            keys.stream_delivery(),
            {"alert_id": alert_id, "recipient_ids": json.dumps(chunk)},
            maxlen=settings.stream_maxlen, approximate=True,
        )
```

A 340-unit alert with `BATCH=100` costs **4 XADDs**, not 340.

## 6.3 Crash-safe consumption

```python
async def worker_loop(consumer: str):
    while not shutdown.is_set():
        msgs = await redis.xreadgroup(
            keys.group(), consumer, {keys.stream_delivery(): ">"},
            count=settings.xread_count, block=settings.xread_block_ms,
        )
        for _, entries in msgs or []:
            for msg_id, fields in entries:
                try:
                    await process_batch(fields)
                    await redis.xack(keys.stream_delivery(), keys.group(), msg_id)
                except Exception:
                    logger.exception("batch_failed", extra={"msg_id": msg_id})
                    # NOT acked → reclaimed by XAUTOCLAIM after idle timeout
```

**A worker dying mid-send loses nothing.** In a system where a dropped alert is a death, at-least-once delivery is a requirement, not a nicety.

## 6.4 **[v3.0] Assistance queue ordering, at one command per batch**

```python
async def enqueue_assistance(cases: list[AssistanceCase]) -> None:
    """One ZADD for the whole batch — §1.4's budget depends on this being a batch call."""
    if not cases:
        return
    await redis.zadd(keys.zset_assistance(),
                     {str(c.id): float(c.priority_score) for c in cases})

async def top_open_cases(limit: int) -> list[int]:
    ids = await redis.zrevrange(keys.zset_assistance(), 0, limit - 1)
    return [int(i) for i in ids]
```

**Postgres remains the source of truth** for `assistance_case`; Redis holds only the hot ordering, exactly as v2.1 §1.3 decided for delivery state. If Redis is flushed, the queue rebuilds from `SELECT id, priority_score FROM assistance_case WHERE status <> 'closed'` — one query, no data loss. That rebuild path is a tested function (`tests/integration/test_assistance_rebuild.py`), not an assumption.

---

# PART 7 — THE DELIVERY STATE MACHINE

## 7.1 States and legal transitions (v2.1 — **unchanged in v3.0, deliberately**)

```
pending ──queue──▶ queued ──dispatch──▶ sent ──provider_cb──▶ delivered
                                          │                       │
                                          │                       └──user_tap──▶ acknowledged ✅
                                          ├──provider_err──▶ failed
                                          │                       │
                                          │                  (attempt < max) ──▶ pending
                                          │                       │
                                          │                  (attempt = max) ──▶ escalated ──▶ pending
                                          └──ttl_exceeded──▶ expired
```

```python
LEGAL: dict[State, frozenset[State]] = {
    State.pending:      frozenset({State.queued, State.expired}),
    State.queued:       frozenset({State.sent, State.failed, State.expired}),
    State.sent:         frozenset({State.delivered, State.failed, State.expired}),
    State.delivered:    frozenset({State.acknowledged, State.expired}),
    State.failed:       frozenset({State.pending, State.escalated, State.expired}),
    State.escalated:    frozenset({State.pending}),
    State.acknowledged: frozenset(),          # terminal
    State.expired:      frozenset(),          # terminal
}

async def transition(db, delivery_id: int, to: State, **ctx) -> None:
    async with db.transaction():
        cur = await db.fetchrow(
            "SELECT state, attempt FROM delivery WHERE id=$1 FOR UPDATE", delivery_id)
        frm = State(cur["state"])
        if to not in LEGAL[frm]:
            raise IllegalTransition(f"{frm} → {to}")
        await db.execute(
            "UPDATE delivery SET state=$2, "
            f"{TIMESTAMP_COL[to]}=now() WHERE id=$1", delivery_id, to.value)
        await append_audit(db, delivery_id=delivery_id,
                           event_type=f"delivery.{to.value}", payload=ctx)
```

### **[v3.0] The most important design decision in this release: the state machine does not change.**

`services/delivery/state_machine.py` is the one module with a **95% branch-coverage floor** (Part 13) and four property tests guarding it. Adding six new assurance tiers to `delivery_state` would have meant rewriting the `LEGAL` table, invalidating those tests, and re-earning that coverage — in seven days, alongside sixteen other features. That is how hackathon projects break their own core.

Instead: **`delivery.state` remains the coarse, transactional lifecycle. `delivery_event` is an additive, append-only evidence log alongside it.** They answer different questions:

| Question | Answered by |
|---|---|
| "What is this delivery *doing* right now — retry? escalate? expire?" | `delivery.state` (8 values, 1 row, FOR UPDATE-locked) |
| "What do we actually have *evidence* for?" | `delivery_event` (6 tiers, N rows, append-only) |

The mapping is deliberately loose and one-directional: `assurance.record()` is called *from* the adapters and webhooks, and **never** drives a state transition on its own. The one exception is explicit and tested: an `acknowledged` assurance event calls `transition(..., State.acknowledged)` inside the same transaction, because that *is* the existing ack path — it is not a new behaviour, just a new writer for an old one.

**Property test that guards the seam** (`tests/property/test_assurance_state_seam.py`):
```python
@given(events=st.lists(st.sampled_from(list(AssuranceEvent))))
def test_assurance_events_never_produce_illegal_states(events):
    """No sequence of provider callbacks, in any order, with any duplicates,
       can drive delivery.state into an illegal transition. Webhooks arrive
       out of order and duplicated in the real world; this proves we survive it."""
```

### **[v3.0] Superseded versions and in-flight deliveries (F2)**

When v2 supersedes v1, what happens to v1 deliveries still retrying? Answered with **zero new states**, because the existing `LEGAL` table already permits it:

```python
async def supersede(db, old_alert_id: int, new_alert_id: int, reason: str) -> None:
    async with db.transaction():
        await db.execute("UPDATE alert SET lifecycle_status='superseded' WHERE id=$1", old_alert_id)
        if await config.get_bool(db, "versioning.cancel_inflight_on_supersede"):
            # pending → expired and queued → expired are BOTH already legal (§7.1).
            # Already-sent deliveries are left alone: you cannot unsend a message,
            # and pretending otherwise would corrupt the ledger.
            rows = await db.fetch(
                "SELECT id FROM delivery WHERE alert_id=$1 AND state IN ('pending','queued')",
                old_alert_id)
            for r in rows:
                await transition(db, r["id"], State.expired, reason="superseded_by_version")
        await append_audit(db, alert_id=old_alert_id, event_type="alert.superseded",
                           payload={"superseded_by": new_alert_id, "reason": reason,
                                    "inflight_cancelled": len(rows)})
```

**Why this is worth a slide:** it is the difference between "we send updates" and "we make sure nobody acts on a stale evacuation instruction." A citizen whose phone was offline when v1 (Moderate) was sent, and who reconnects after v3 (Extreme, evacuate) is live, must receive v3 — not v1 from a retry queue. That is a real, documented failure mode of broadcast systems, and the fix is nine lines because the state machine was designed properly in v2.0.

## 7.2 Escalation — fully policy-driven (v2.1, unchanged)

```python
async def on_failure(db, delivery: Delivery) -> None:
    policy = await policies.for_severity(db, delivery.alert.severity)
    step = policy.step_for(delivery.channel_id)

    if delivery.attempt < step.max_attempts:
        await transition(db, delivery.id, State.pending, retry_of=delivery.attempt)
        await schedule_retry(delivery.id, delay_s=backoff(delivery.attempt, step))
        return

    if (nxt := policy.next_step(step.step_order)) is not None:
        await transition(db, delivery.id, State.escalated, next_channel=nxt.channel_id)
        await create_delivery(db, delivery.alert_id, delivery.recipient_id, nxt.channel_id)
    else:
        await transition(db, delivery.id, State.expired, reason="channels_exhausted")
```

Nothing above contains a number. Change escalation behaviour with an `UPDATE`.

## 7.3 Pre-emptive escalation — where the ML pays off (v2.1, unchanged)

```python
async def initial_channel_for(db, unit_id: int, alert: Alert) -> int:
    """High reach-risk units skip straight to a resilient channel —
       BEFORE the towers go down. This is the Palghar fix."""
    risk = await reach.risk_for(db, alert.id, unit_id)
    policy = await policies.for_severity(db, alert.severity)
    for step in policy.steps:
        if step.applies_if_reach_risk_gte is None or risk >= step.applies_if_reach_risk_gte:
            return step.channel_id
    return policy.steps[0].channel_id
```

## 7.4 **[v3.0] `channels_exhausted` is no longer the end of the line**

In v2.1, a delivery that exhausted every channel became `expired` and the story ended — the platform had done all it could, and a red dot on a map was the only output. v3.0 adds one branch, and it is the entire point of B9:

```python
async def on_channels_exhausted(db, delivery: Delivery) -> None:
    """The last digital channel failed. Before giving up, check for a human."""
    if not await config.get_bool(db, "relay.escalate_on_channels_exhausted"):
        return
    node = await db.fetchrow(
        "SELECT id FROM relay_node WHERE unit_id=$1 AND active LIMIT 1", delivery.unit_id)
    if node is None:
        # Honest terminal state — and a preparedness finding, surfaced in D8f (§4.7).
        await append_audit(db, delivery_id=delivery.id,
                           event_type="relay.unavailable",
                           payload={"unit_id": delivery.unit_id,
                                    "reason": "no_active_relay_node"})
        return
    await create_delivery(db, delivery.alert_id, delivery.recipient_id,
                          channel_id=await channels.id_of(db, "human_relay"))
```

**`relay.unavailable` is a first-class audit event, not a silent no-op.** "We could not reach this village and there is no registered human who could" is the single most actionable line a post-incident report can contain, and it is the honest answer to the question that started this whole review: *what if the alert reaches nobody, and how would we know?* We know, we record it, and D8f names the village before the next disaster.

---

# PART 8 — CHANNEL ADAPTERS

## 8.1 The contract **[v3.0 — capability declaration added]**

```python
class ChannelAdapter(Protocol):
    code: str
    # [v3.0] These four are DECLARED here and MIRRORED in channel_capability (§5.2).
    # A CI test asserts the code and the table agree — a drift between them is exactly
    # how a channel starts silently claiming a tier it cannot prove (Rule 8).
    supports_provider_accept: bool
    supports_device_delivered: bool
    supports_opened: bool
    supports_acknowledgement: bool

    async def send(self, msg: OutboundMessage) -> SendResult: ...
    async def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> list[StatusUpdate]: ...
```

## 8.2 **[v3.0] The capability matrix — the honesty table, as data**

This is `data/seeds/channel_capability.sql`. **The UI reads it; nothing is hardcoded in TypeScript.** `not_applicable_reason` is rendered verbatim to the officer.

| Channel | 1 provider_accepted | 2 device_delivered | 3 opened | 4 acknowledged | How device_delivered is proven |
|---|---|---|---|---|---|
| **fcm** | ✅ | ✅ | ✅ | ✅ | **Our own service worker calls home.** FCM does not report delivery to the sender. |
| **sms** | ✅ | ✅ | ❌ | ✅ | **Twilio carrier status callback** = `delivered`. A genuine telecom confirmation. |
| **ivr** | ✅ | ✅ | ❌ | ✅ | **`CallStatus=in-progress`** — a human physically answered. Strongest signal we have. |
| **email** | ✅ | ⚠️ | ❌ | ✅ | Provider-dependent; **open-pixel tracking deliberately disabled** — see below. |
| **siren** | ✅ | ❌ | ❌ | ❌ | Nothing. A physical broadcast emits no receipt. |
| **human_relay** | ✅ | ✅ | ❌ | ✅ | Relay node answered the call. Confirmation is `confirmed_by_human` (Rule 9). |
| **community_relay** | ➖ | ✅ | ✅ | ✅ | Peer device's GATT write completed + signature verified, synced on reconnect. |
| **sim** | ✅ | ✅ | ✅ | ✅ | **All simulated.** Every row `simulated=true`, `SIM` badge on screen (§8.5). |

```sql
INSERT INTO channel_capability
 (channel_id, supports_provider_accept, supports_device_delivered, supports_opened,
  supports_acknowledgement, device_delivered_source, not_applicable_reason) VALUES
 (1, true,  true,  true,  true,  'pwa_service_worker_callback', NULL),
 (2, true,  false, false, true,  NULL,
     'Email open tracking requires a tracking pixel. We do not use one: it is a privacy '
     'intrusion, it is blocked by most clients, and a blocked pixel is indistinguishable '
     'from an unopened email — so the signal would be unreliable as well as invasive.'),
 (3, true,  true,  false, true,  'twilio_carrier_status_callback',
     'No mobile carrier exposes SMS read receipts to the sender. This tier cannot be '
     'measured for SMS by anyone, including us.'),
 (4, true,  true,  false, true,  'twilio_call_status_in_progress',
     'A voice call has no "opened" concept. Answering the call is the delivery, and the '
     'keypad press is the acknowledgement.'),
 (5, true,  false, false, false, NULL,
     'A siren or public-address broadcast produces no digital receipt of any kind. '
     'Confirmation requires a human — see the field relay channel.'),
 (6, true,  true,  true,  true,  'simulated_carrier_profile',
     NULL),
 (7, true,  true,  false, true,  'relay_node_answered_call',
     'A physical, door-to-door broadcast has no "opened" event. The relay operator''s '
     'keypad confirmation is a human attestation, recorded separately from digital delivery.'),
 (8, false, true,  true,  true,  'peer_gatt_write_signature_verified',
     'A peer-to-peer transfer never touches our server, so there is no provider to accept '
     'it. Delivery is proven by the receiving device, reported when it reconnects.');
```

**The email decision is worth defending out loud.** We *could* implement open tracking and claim a fourth tier. We chose not to, and the reason is in the database where a judge can read it: a tracking pixel is both a privacy intrusion and an unreliable signal. **Declining to measure something you could measure badly is a stronger engineering statement than measuring it.**

## 8.3 FCM — the primary channel **[v3.0: the device-delivered correction]**

```python
class FcmAdapter:
    code = "fcm"
    supports_provider_accept = True
    supports_device_delivered = True     # via OUR callback, not via FCM
    supports_opened = True
    supports_acknowledgement = True

    async def send(self, msg):
        payload = {"message": {
            "token": msg.address,
            "notification": {"title": msg.headline, "body": msg.body},
            "data": {"alert_id": str(msg.alert_id),
                     "delivery_id": str(msg.delivery_id),
                     "ack_url": msg.ack_url,
                     "receipt_nonce": msg.receipt_nonce,     # [v3.0] anti-replay for the SW callback
                     "signature": b64(msg.signature)},       # [v3.0] Rule 11, verified by the PWA
            "android": {"priority": "high"},
            "webpush": {"headers": {"Urgency": "high"}}}}
        r = await self._client.post(self._endpoint, json=payload,
                                    headers=await self._auth_headers())
        r.raise_for_status()
        await assurance.record(self._db, msg.delivery_id, "provider_accepted",
                               source="fcm_send", evidence_id=r.json()["name"])
        return SendResult(provider_ref=r.json()["name"], simulated=False)
```

```python
# services/api/routers/receipts.py — [v3.0] the ONLY real device-delivered signal for push.
@router.post("/api/v1/deliveries/{delivery_id}/receipt")
async def sw_receipt(delivery_id: int, body: ReceiptIn, db=Depends(get_db)):
    """Called by the citizen PWA's service worker on 'push' and on 'notificationclick'.
       Nonce-checked so a replayed or guessed delivery_id cannot forge a receipt."""
    if not await receipts.nonce_valid(db, delivery_id, body.receipt_nonce):
        raise HTTPException(403, detail={"code": "invalid_receipt_nonce"})
    tier = "notification_opened" if body.event == "click" else "device_delivered"
    await assurance.record(db, delivery_id, tier, source="client_sw",
                           evidence_id=body.receipt_nonce)
    return {"recorded": tier}
```

**The nonce matters.** Without it, `delivery_id` is a sequential integer and anyone could POST receipts for deliveries that never arrived — inflating the exact metric the pitch leads with. The nonce is generated per delivery, sent inside the FCM data payload, and single-use.

## 8.4 SMS and IVR — real adapters, honest constraints **[v3.0: webhooks wired to the ladder]**

```python
class TwilioSmsAdapter:
    code = "sms"
    supports_provider_accept = True
    supports_device_delivered = True      # Twilio carrier status callback — a real signal
    supports_opened = False               # no carrier on earth gives this (§8.2)
    supports_acknowledgement = True       # inbound keyword, or a tapped link into the PWA

    async def send(self, msg):
        # Trial accounts reach VERIFIED numbers only. India domestic additionally requires
        # DLT registration (~10 business days, registered legal entity). Documented, not worked around.
        if not await self._is_verified(msg.address):
            raise ChannelUnavailable(
                "recipient_not_verified_on_trial",
                remediation="Route to SimulatedCarrierAdapter and mark simulated=true")
        r = await self._client.messages.create(
            to=msg.address, from_=self._from, body=msg.body,
            status_callback=f"{self._public_base}/api/v1/webhooks/sms-status")
        await assurance.record(self._db, msg.delivery_id, "provider_accepted",
                               source="twilio_sms_send", evidence_id=r.sid)
        return SendResult(provider_ref=r.sid, simulated=False)
```

```python
# [v3.0] Provider callbacks — HMAC-verified (Part 12), idempotent by §5.7's unique index.
@router.post("/api/v1/webhooks/sms-status")
async def sms_status(req: Request, db=Depends(get_db)):
    body = await verify_twilio_signature(req)            # unsigned → 401, Part 12
    delivery_id = await deliveries.by_provider_ref(db, body["MessageSid"])
    match body["MessageStatus"]:
        case "delivered":
            await assurance.record(db, delivery_id, "device_delivered",
                                   source="twilio_sms_webhook", evidence_id=body["MessageSid"])
        case "undelivered" | "failed":
            await on_failure(db, await deliveries.get(db, delivery_id))   # existing escalation path
    # "opened" is NEVER written here. channel_capability.supports_opened = false for SMS.
    return Response(status_code=204)

@router.post("/api/v1/webhooks/ivr-status")
async def ivr_status(req: Request, db=Depends(get_db)):
    body = await verify_twilio_signature(req)
    delivery_id = await deliveries.by_provider_ref(db, body["CallSid"])
    if body.get("CallStatus") == "in-progress":
        # A human physically answered. The strongest device_delivered signal in the platform.
        await assurance.record(db, delivery_id, "device_delivered",
                               source="twilio_call_webhook", evidence_id=body["CallSid"])
    if (digits := body.get("Digits")):
        # DTMF maps straight onto C6's response taxonomy — same table, same queue.
        await response_service.record_from_dtmf(db, delivery_id, digits)
    return Response(status_code=204)
```

**The DTMF→C6 mapping is the feature that makes structured response reachable without a smartphone.** `1 = I'm safe`, `2 = I need help`, then `1 = trapped · 2 = medical · 3 = cannot evacuate`. Same `citizen_response` rows, same `assistance_case` queue, same priority formula — a feature-phone user with no data connection produces an identical operational outcome to a PWA user. That is the single strongest equity argument in the product, and it costs one `<Gather>` verb.

## 8.5 The simulated adapter — and why it is honest, not a cheat (v2.1, unchanged)

```python
class SimulatedCarrierAdapter:
    """Models a real carrier: latency distribution, partial failure, silent drops.
       Every delivery it produces is flagged simulated=true in the DB and
       rendered with a visible 'SIM' badge in the console. We never pretend."""
    code = "sim"

    async def send(self, msg):
        profile = self._profiles[msg.channel_code]          # from config, not literals
        await asyncio.sleep(profile.sample_latency())
        outcome = profile.sample_outcome()                  # delivered / failed / silent
        if outcome is Outcome.FAILED:
            raise TransientChannelError(profile.sample_error())
        return SendResult(provider_ref=f"sim-{uuid4()}", simulated=True)
```

> **Pitch language, verbatim:**
> *"Three villages in this demo are wired to real phones in this room — you'll see real push notifications and a real SMS arrive. The other 337 run the identical delivery engine, state machine and escalation logic against a simulated carrier, because reaching real SIM cards nationally requires the same TRAI DLT registration SACHET itself uses, which needs a registered legal entity and ten business days. Everything you see marked SIM is flagged in our database and on screen. We didn't hide it — we built the boundary explicitly."*

## 8.6 **[v3.0] The Human Relay adapter (B9)**

```python
class HumanRelayAdapter:
    """Channel of last resort. Places an IVR call to a REGISTERED relay node — a panchayat
       office, police station, school, ASHA worker — asking a human to physically inform the
       households the digital channels could not reach, and to confirm when done.

       Rule 9: what this produces is a HUMAN ATTESTATION, stored in relay_confirmation,
       never written as a digital delivery event for the citizen."""
    code = "human_relay"
    supports_provider_accept   = True     # the call was placed
    supports_device_delivered  = True     # the relay operator answered
    supports_opened            = False    # no such concept
    supports_acknowledgement   = True     # the DTMF confirmation

    async def send(self, msg):
        # Node ordering comes from app_config (relay.node_kind_priority) and is applied
        # with array_position — NEVER a CASE expression in SQL. Part 38, violation A.
        kind_order = await config.get_csv(self._db, "relay.node_kind_priority")
        node = await self._db.fetchrow(
            "SELECT id, phone_enc FROM relay_node "
            "WHERE unit_id=$1 AND active "
            "ORDER BY array_position($2::text[], kind) NULLS LAST, id "
            "LIMIT 1",
            msg.unit_id, kind_order)
        if node is None:
            raise ChannelUnavailable("no_relay_node_registered_for_unit")

        phone = await crypto.decrypt_phone(node["phone_enc"])
        twiml_url = f"{self._public_base}/api/v1/ivr/relay-script/{msg.delivery_id}"
        call = await self._twilio.calls.create(
            to=phone, from_=self._from, url=twiml_url,
            status_callback=f"{self._public_base}/api/v1/webhooks/ivr-status")
        await assurance.record(self._db, msg.delivery_id, "provider_accepted",
                               source="relay_ivr", evidence_id=call.sid)
        return SendResult(provider_ref=call.sid, simulated=False)

    async def parse_webhook(self, body, headers):
        if parse_twilio_gather_digit(body) == "1":
            return [StatusUpdate(event="confirmed_by_human", method="ivr_dtmf")]
        return []
```

```xml
<!-- GET /api/v1/ivr/relay-script/{delivery_id} — generated, translated via C3, never hardcoded -->
<Response>
  <Say language="ml-IN">Emergency alert for Meppadi. Severity: extreme.
    Flood warning. Twelve households in your area could not be reached by phone.
    Please inform them directly.</Say>
  <!-- numDigits and timeout are interpolated from app_config (ivr.gather_*), not typed
       into the template — a 10-second wait is a UX decision about a stressed human on a
       phone in a disaster, and it belongs where it can be tuned. Part 38, violation E. -->
  <Gather numDigits="{{ivr.gather_digits}}" timeout="{{ivr.gather_timeout_s}}"
          action="/api/v1/webhooks/ivr-status" method="POST">
    <Say language="ml-IN">Press 1 once you have informed them.</Say>
  </Gather>
  <Say language="ml-IN">No confirmation received. We will call again.</Say>
</Response>
```

**The relay script is generated per unit and translated through C3's existing IndicTrans2 cache** — the relay operator hears Malayalam in Wayanad and Marathi in Palghar, from the same translation table that serves the citizen PWA. One model, two audiences, zero extra cost.

## 8.7 **[v3.0] Community Relay Mode (B10) — and the security that makes it defensible**

Per Trap 12, this is **citizen-initiated**, one tap, no background scanning — the only version a browser permits.

**Server side — every alert is signed at publish time (Rule 11):**
```python
# services/crypto/alert_signing.py
from nacl.signing import SigningKey
import json, base64

CANONICAL_FIELDS = ("id", "incident_id", "version_number", "severity",
                    "headline", "body", "effective_at", "expires_at")

def canonical_bytes(alert: dict) -> bytes:
    """Deterministic serialisation — sorted keys, no whitespace, explicit field order.
       Two servers must produce byte-identical output for the same alert."""
    return json.dumps({k: str(alert[k]) for k in CANONICAL_FIELDS},
                      sort_keys=True, separators=(",", ":")).encode()

def sign_alert(alert: dict) -> bytes:
    sk = SigningKey(base64.b64decode(settings.alert_signing_seed_b64))   # env var, Part 25
    return sk.sign(canonical_bytes(alert)).signature                     # 64 bytes
```
The **public** verify key ships inside the PWA bundle. That is safe — it is a public key, and it is the whole point: a device with no network can still verify authenticity offline.

**Client side — Device A shares, Device B verifies before it trusts anything:**
```typescript
// web/citizen/src/relay.ts — Device A: the citizen taps "Share with someone nearby"
export async function shareNearby(alert: SignedAlert): Promise<void> {
  const device = await navigator.bluetooth.requestDevice({          // requires the tap (Trap 12)
    filters: [{ services: [SETU_RELAY_SERVICE_UUID] }],
  });
  const server = await device.gatt!.connect();
  const svc = await server.getPrimaryService(SETU_RELAY_SERVICE_UUID);
  const ch  = await svc.getCharacteristic(ALERT_PAYLOAD_CHAR_UUID);
  // Chunked: a BLE characteristic write is small and an alert with translations exceeds it.
  // The chunk size is config, not a literal — different Android stacks negotiate different
  // MTUs, so this is a value we will tune on the real demo devices. Part 38, violation D.
  const payload = JSON.stringify({ ...alert, relayed_by: myAnonId });
  for (const chunk of chunkPayload(payload, CFG.relayChunkBytes)) {
    await ch.writeValueWithResponse(chunk);
  }
}
```
```typescript
// web/citizen/src/verify.ts — Device B: NOTHING is displayed before this returns true
import { verify } from '@noble/ed25519';
import { SETU_PUBLIC_KEY } from './signing-key';           // baked into the bundle

export async function acceptRelayed(payload: unknown): Promise<boolean> {
  const alert = parseOrThrow(payload);
  const ok = await verify(alert.signature, canonicalBytes(alert), SETU_PUBLIC_KEY);
  if (!ok) {
    // Rule 11: discard silently, log locally, never render. A fake evacuation order
    // injected over Bluetooth would be worse than no alert at all.
    await localLog.write('relay.signature_invalid', { relayed_by: alert.relayed_by });
    return false;
  }
  await idb.put('setu-alerts-v1', { ...alert, provenance: 'peer_relay', verified: true });
  await bgSync.register('setu-relay-receipt-queue');   // reports the receipt when online again
  return true;
}
```

**Rendered provenance, non-negotiable:** every relayed alert in the citizen UI carries `⇄ Received via a nearby device · signature verified`, and the disclosure *"Peer relay is demonstrated between two devices. Multi-hop mesh relay is future work and is not part of this build."* Same honesty family as the `SIM` badge.

**Three limits stated before a judge finds them:** (1) Web Bluetooth is Chromium-only — **not iOS Safari** (same constraint as the offline PWA, Part 11.4; present on Android, decided by Day 8). (2) It is **one hop**, not a mesh — B relays to nobody automatically. (3) It **requires a deliberate human tap** — which we consider correct product design for a person choosing to warn a neighbour, and which is also the only thing the platform allows.
---

# PART 9 — MACHINE LEARNING

**[v3.0] states one thing up front: this release adds ZERO new models.** Seventeen new features, no new ML. That is deliberate and it is a defensible engineering position: every new "intelligence" feature in v3.0 is either a **deterministic, config-weighted formula whose inputs are stored** (D11f priority, F4 fatigue, D8f vulnerability) or a **surfacing of a model we already have** (D12f explanation). Part 35 records the one proposal we rejected specifically because it *would* have needed a new model trained on data we will not have by demo day (Channel Reliability Intelligence). *"Do not add AI because it sounds impressive — add intelligence only where it changes an operational decision"* is now a build rule, not a slogan.

## 9.1 Model 1 — Cross-agency alert deduplication *(real data, real evaluation)*

**Problem:** NDMA, IMD, CWC and a state DMA issue alerts about one event, worded differently, sometimes in different languages. Naive string matching fails.

- **Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` → cosine similarity → agglomerative clustering with a distance threshold **loaded from config**.
- **Guard:** only cluster alerts whose areas intersect (`ST_Intersects`) and whose effective windows overlap. Semantic similarity alone is not sufficient evidence.
- **Evaluation:** collect real CAP alerts over the build window, hand-label ~200 pairs, report **precision / recall / F1 on a held-out split.**

```python
async def cluster(alerts: list[Alert], cfg: DedupConfig) -> list[Cluster]:
    emb = model.encode([f"{a.headline} {a.body}" for a in alerts], normalize_embeddings=True)
    sim = emb @ emb.T
    for i, j in itertools.combinations(range(len(alerts)), 2):
        if not (await areas_intersect(alerts[i], alerts[j]) and windows_overlap(alerts[i], alerts[j])):
            sim[i][j] = sim[j][i] = 0.0          # spatial/temporal veto
    return agglomerate(sim, threshold=cfg.similarity_threshold)
```

**[v3.0] Dedup now feeds F2.** A cluster of alerts about one event is exactly an `incident`. `services/ingestion/incident_linker.py` takes the dedup cluster and either attaches the new alert as **version N+1 of an existing incident** or **opens a new incident** — which means the dedup model, previously a de-duplication nicety, is now the mechanism that keeps an evolving disaster coherent. Same model, no retraining, substantially more product value.

```python
async def link_to_incident(db, alert: Alert, cluster_id: int | None) -> int:
    if cluster_id:
        existing = await db.fetchrow(
            "SELECT incident_id, MAX(version_number) AS v FROM alert "
            "WHERE cluster_id=$1 AND incident_id IS NOT NULL GROUP BY incident_id", cluster_id)
        if existing:
            return existing["incident_id"]      # new version of a known incident
    inc = await db.fetchrow(
        "INSERT INTO incident (label, incident_type, origin_source) "
        "VALUES ($1,$2,$3) RETURNING id",
        await labels.generate(db, alert),        # 'WAYANAD-FLOOD-001' — generated, never typed
        alert.hazard_type, alert.source_id)
    return inc["id"]
```

## 9.2 Model 2 — Reach-failure prediction *(and the honest problem with it)*

**⚠️ State the problem before a judge finds it.** This model should learn from historical acknowledgement outcomes — but **no system has ever tracked acknowledgement, so that history does not exist.** We address it head-on.

**Stage 1 — Bootstrap model (ships for the demo).** Trained on a **physically-grounded generative process**, not invented labels. Features are all real and measured:

| Feature | Source | Verified? |
|---|---|---|
| `terrain_ruggedness` | Copernicus GLO-30, SRTM fallback | ✅ (four-tile check, Part 29) |
| `nearest_tower_km`, `tower_count_5km` | OpenCelliD | ✅ free token; **5-feature fallback if approval slips, Part 30** |
| `population`, `building_count` | WorldPop, Open Buildings | ✅ CC BY 4.0 |
| `alert_severity`, `hour_of_day` | Alert itself | ✅ |
| `rainfall_intensity` | Open-Meteo precipitation | ✅ no IMD dependency |

The label comes from an **explicit, published failure model** — *P(fail) rises with rainfall intensity × inverse tower density × terrain ruggedness* — coefficients documented in the repo. **`model_registry.is_bootstrap = true`, and the UI renders a "bootstrap model" badge next to every risk score.**

**Stage 2 — Case-study validation.** Run the bootstrap model on **Wayanad (Jul 2024)** and **Palghar (Jul 2026)** with their real terrain, tower and rainfall features. Did it flag those units as high-risk? Report as a case study of **n = 2, and say n = 2 out loud.**

**Stage 3 — Online learning (architecture ships, data accrues).** Every real acknowledgement outcome writes a labelled row. `model_registry` supports versioning and A/B activation.

```python
class ReachRiskModel:
    def predict(self, feats: pd.DataFrame) -> np.ndarray:
        return self._booster.predict_proba(feats[self._feature_order])[:, 1]

    @property
    def disclosure(self) -> str:
        return ("Bootstrap model. Trained on a published physical failure process, "
                "not on historical acknowledgement outcomes, because no system has "
                "previously recorded them. Validated as a case study against "
                "Wayanad 2024 and Palghar 2026 (n=2).")
```

**[v3.0] Two things changed around this model, neither of them the model itself:**

1. **D12f surfaces `reach_prediction.features` in the UI.** The explainability data was already stored (v2.1 schema); it was simply never rendered. Rule 10 now makes storing-without-showing a defect.
2. **Stage 3 finally has a real label source.** v2.1's online-learning path was architecturally sound but data-starved. B8's `delivery_event` rows and C6's `citizen_response` rows are exactly the acknowledgement outcomes the model needs — so v3.0 does not improve the model, but it **builds the pipe that eventually will**, and that is an honest thing to say on a slide: *"we did not train a better model this week; we built the instrument that collects the data no one has ever collected."*

**DEM plan, in order:** (1) Copernicus GLO-30 via the confirmed no-auth S3 bucket; (2) SRTM 30m fallback per-cell; (3) coarse ruggedness proxy; (4) **drop the feature entirely rather than fake it.** A model with 5 honest features beats one with 6 where one is invented.

## 9.3 Model 3 — Translation *(pretrained, no training required)*

**`ai4bharat/indictrans2-en-indic-dist-200M`** (not the 1B — Trap 10). 0.3B params, MIT, CPU-feasible, all 22 scheduled languages. Served from the ML microservice on Hugging Face Spaces (Part 22); translations **cached in Postgres keyed by `(alert_id, target_lang)`** — translate once, serve many. Falls back to the original language with a visible notice; never blocks delivery.

**[v3.0] Two new consumers of the same cache, zero new cost:** the B9 relay IVR script (§8.6) and the C6 response prompts. `alert_translation` is now read by the citizen PWA, the IVR `<Say>` verb, and the relay script — one translation, three delivery surfaces.

## 9.4 Model 4 *(stretch)* — Disaster Copilot, RAG with strict grounding

- Index NDMA SOPs, dam EAPs, shelter registries into **pgvector** (free on every Neon plan).
- Retrieval → LLM with a system prompt that **forbids answering outside retrieved context** and **requires citations**.
- Below a configured retrieval-confidence floor it says *"I don't have a document covering that"* — it does not guess.

**Document sourcing status — `[UNVERIFIED]`, with the concrete fallback list in Part 31.** This feature is [S] stretch and independently cuttable. **In a disaster tool, a hallucinated protocol is worse than no answer.**

## 9.5 Model 5 — Thunderstorm/convective nowcast classifier

**Data:** Open-Meteo CAPE, Lifted Index, CIN (confirmed free, global, no key) + precipitation probability, per admin-unit centroid.
**Model:** rule-based with documented, meteorologically-standard thresholds from config; upgrades to LightGBM once labelled outcomes accrue.

```python
class ThunderstormClassifier:
    def risk(self, row: dict, cfg: ThunderstormConfig) -> float:
        return (_sigmoid((row["cape"] - cfg.cape_floor) / cfg.cape_scale) *
                _sigmoid((cfg.li_ceiling - row["lifted_index"]) / cfg.li_scale) *
                row["precipitation_probability"])

    @property
    def disclosure(self) -> str:
        return ("Threshold model on live CAPE/Lifted-Index/CIN from Open-Meteo — "
                "the same convective indices meteorologists use, not a proprietary feed. "
                "Upgrades to a trained classifier as real outcomes accrue.")
```

**[v3.0] Rule 12 consequence, worth stating explicitly:** because this is *our own* model rather than an external authority, `alert_source.is_authoritative = false` for `thunderstorm_nowcast`. **A severe or extreme thunderstorm alert generated by our own classifier requires two human approvals before dispatch.** Our model does not get to authorize itself. This is the single clearest demonstration that Module F is a real governance layer and not decoration.

## 9.6 **[v3.0] The three "intelligence" features that are deliberately not models**

| Feature | What it actually is | Why not a model |
|---|---|---|
| **D11f assistance priority** | A **weighted sum of five normalised factors**, weights in `app_config`, every factor value stored in `priority_factors` (Rule 10) | With zero historical triage outcomes, a learned ranker would be a black box fitted to nothing. A weighted sum can be *explained to the officer whose decision it changes* — and Gap E's own advice was "do not use an unexplained black-box score." |
| **F4 alert fatigue** | A **`COUNT` over a config-driven window** | Fatigue is a counting question, not a prediction question. |
| **D8f communication vulnerability** | A **three-ground rule** over already-computed `unit_features`, reporting *which* grounds fired | The reach-risk model already does the prediction. This is the complementary *structural* view — persistent dead zones, not per-alert risk — and it must be legible to a district officer planning next year's relay coverage. |

```python
# services/response/priority.py — Rule 10 in code: every factor value is returned, not just the score.
async def compute_priority(db, resp: CitizenResponse) -> tuple[float, dict]:
    w = await config.get_weights(db, prefix="assistance.weight.")     # from app_config
    sev = await config.get_map(db, prefix="assistance.response_severity.")
    factors = {
        "response_severity": sev[resp.response_type],
        "hazard_severity":   await config.get_float(db, f"severity.rank.{resp.alert_severity}"),
        "vulnerability":     await reach.risk_for(db, resp.alert_id, resp.unit_id),
        "proximity":         1 - await geo.normalised_distance_to_hazard(db, resp),
        "time_waiting":      min(1.0, minutes_since(resp.received_at)
                                 / await config.get_float(db, "assistance.max_wait_minutes")),
    }
    score = sum(w[k] * v for k, v in factors.items())
    return score, {"weights": w, "factors": factors,
                   "formula": "sum(weight_i * factor_i)",
                   "model_version": await config.get_str(db, "assistance.weight_version")}
```
The officer-facing UI renders that dict as a readable breakdown. **"Why is this case first?"** has an answer on screen, every time — which is both better product and a better answer in Q&A than any learned ranker we could have trained this week.

---

# PART 10 — API CONTRACT

```
── Alerts & incidents ─────────────────────────────────────────────────────────
POST   /api/v1/alerts                       Create draft alert (officer+)
GET    /api/v1/alerts                       List, filter by state/severity/time
GET    /api/v1/alerts/{id}                  Detail + targeting summary
POST   /api/v1/alerts/{id}/preview          Exposure preview — no send
POST   /api/v1/alerts/{id}/validate         [v3.0] F1 — run the quality gate, return per-rule results
POST   /api/v1/alerts/{id}/approve          [v3.0] F3 — record one approval/rejection (officer+)
POST   /api/v1/alerts/{id}/dispatch         Fan out (officer+, Idempotency-Key required)
                                            [v3.0] 422 if the gate fails · 409 if approvals are short
POST   /api/v1/alerts/{id}/new-version      [v3.0] F2 — draft vN+1, supersedes vN on publish
GET    /api/v1/alerts/{id}/deliveries       Paginated delivery rows
GET    /api/v1/alerts/{id}/assurance        [v3.0] B8 — per-channel ladder rollup + not_applicable
GET    /api/v1/alerts/{id}/audit            Full hash-chained ledger
GET    /api/v1/alerts/{id}/report.pdf       Post-event audit report

GET    /api/v1/incidents                    [v3.0] List incidents
GET    /api/v1/incidents/{id}               [v3.0] Detail + full version chain
GET    /api/v1/incidents/{id}/timeline      [v3.0] D10f — chronological operational record
GET    /api/v1/incidents/{id}/board         [v3.0] D9f — command board rollup, one payload
POST   /api/v1/incidents/{id}/close         [v3.0] Close (state_admin+); triggers D14f

── Citizen ────────────────────────────────────────────────────────────────────
POST   /api/v1/ack                          Acknowledgement (idempotent) — v2.1, retained
POST   /api/v1/response                     [v3.0] C6 — structured response (idempotent)
POST   /api/v1/deliveries/{id}/receipt      [v3.0] B8 — service-worker receipt, nonce-checked
POST   /api/v1/relay/receipt                [v3.0] B10 — peer-relay receipt, synced on reconnect

── Assistance ─────────────────────────────────────────────────────────────────
GET    /api/v1/assistance                   [v3.0] D11f — open cases, priority-ordered
GET    /api/v1/assistance/{id}              [v3.0] Case detail incl. priority_factors breakdown
PATCH  /api/v1/assistance/{id}              [v3.0] Assign / advance status (officer+)

── Relay ──────────────────────────────────────────────────────────────────────
GET    /api/v1/relay/tasks                  [v3.0] B9 — open relay tasks (relay_node role)
POST   /api/v1/relay/tasks/{id}/confirm     [v3.0] B9 — human confirmation (console path)
GET    /api/v1/ivr/relay-script/{id}        [v3.0] B9 — TwiML, translated, generated

── Enrollment ─────────────────────────────────────────────────────────────────
POST   /api/v1/admin/recipients/import      [v3.0] E4 — CSV, ?dry_run=true supported (officer+)
POST   /api/v1/webhooks/sms-inbound         [v3.0] E4 — REGISTER / STOP keywords (HMAC-verified)

── Webhooks (HMAC-verified, never user-authenticated) ─────────────────────────
POST   /api/v1/webhooks/sms-status          [v3.0] Twilio carrier delivery receipts
POST   /api/v1/webhooks/ivr-status          [v3.0] Call status + DTMF
POST   /api/v1/webhooks/{channel_code}      Generic provider callbacks

── Geography & analytics ──────────────────────────────────────────────────────
GET    /api/v1/units                        Admin units, bbox-filtered, GeoJSON
GET    /api/v1/units/{id}/risk              Reach-risk + [v3.0] D12f top_factors + recommended_action
GET    /api/v1/units/{id}/reachability      [v3.0] D7f — both denominators + geometry_level label
GET    /api/v1/units/{id}/vulnerability     [v3.0] D8f — primary_factors[] + recommended_fallback
GET    /api/v1/analytics/summary            Ack rates by district/channel/time
GET    /api/v1/analytics/lead-time          [v3.0] D13f — percentiles + its own coverage_pct
GET    /api/v1/incidents/{id}/after-action  [v3.0] D14f — measurement-cited recommendations

── Platform ───────────────────────────────────────────────────────────────────
GET    /api/v1/models                       Registry + metrics + bootstrap flags
GET    /api/v1/methodology                  Every threshold, model and limitation, as JSON
                                            [v3.0] now also every channel_capability row
WS     /ws/alerts/{id}                      Live delivery updates
WS     /ws/incidents/{id}                   [v3.0] Command-board + assistance-queue updates
GET    /health                              Liveness (also the keep-warm target)
```

**`/api/v1/methodology` is a deliberate feature, and [v3.0] makes it stronger.** It now returns the entire `channel_capability` table — meaning *"here is every signal we can prove, every signal we cannot, and the reason for each"* is a **machine-readable public artifact**, not a claim in a pitch. If one endpoint should be open in a browser tab during Q&A, it is this one.

**Idempotency.** `POST /dispatch`, `/ack`, `/response`, `/approve` all require an `Idempotency-Key`; replays return the original result. A citizen tapping "I'm safe" five times on a flaky connection must not create five rows — and **[v3.0]** an officer double-clicking Approve must not satisfy a two-approval quorum by itself (though `UNIQUE (alert_id, approver_id)` in §5.5 is the real guarantee; idempotency is just the clean error).

**[v3.0] Status-code contract for the governance gate**, so the frontend has no ambiguity:

| Condition | Code | Body |
|---|---|---|
| Quality gate failed | `422` | `{"error":"validation_failed","code":"quality_gate","failures":[{"rule_id":"expiry_set","message":"No expiry timestamp set"}]}` |
| Approvals short of quorum | `409` | `{"error":"awaiting_authorization","code":"approval_quorum","have":1,"need":2}` |
| Another version publishing (Redis lock) | `409` | `{"error":"version_in_flight","code":"supersede_locked","retry_after_ms":500}` |
| Alert already superseded | `409` | `{"error":"stale_version","code":"superseded","active_version":3}` |
| Not the officer's district | `403` | `{"error":"forbidden","code":"unit_scope"}` |

Every one of these is a **distinct, testable branch** — Part 13 has a test per row. A generic 400 for all five would have been faster to write and impossible to debug on stage.

---

# PART 11 — FRONTEND & DESIGN SYSTEM

Two apps, one token package. Console is **dark-first, high-density** (Linear / Datadog / PagerDuty lineage). Citizen PWA is **light-first, large-touch, calm**.

## 11.1 Design tokens (v2.1, + v3.0 assurance/governance tokens)

```ts
// packages/tokens/src/index.ts — semantic, never raw hex in components
export const severity = {
  extreme:  { bg: 'var(--sev-extreme-bg)',  fg: 'var(--sev-extreme-fg)',  icon: 'AlertOctagon' },
  severe:   { bg: 'var(--sev-severe-bg)',   fg: 'var(--sev-severe-fg)',   icon: 'AlertTriangle' },
  moderate: { bg: 'var(--sev-moderate-bg)', fg: 'var(--sev-moderate-fg)', icon: 'AlertCircle' },
  minor:    { bg: 'var(--sev-minor-bg)',    fg: 'var(--sev-minor-fg)',    icon: 'Info' },
} as const;

export const deliveryState = {
  acknowledged: { token: 'state-ok',      icon: 'CheckCircle2', label: 'Acknowledged' },
  delivered:    { token: 'state-info',    icon: 'Send',         label: 'Delivered' },
  sent:         { token: 'state-neutral', icon: 'Clock',        label: 'Sent' },
  failed:       { token: 'state-danger',  icon: 'XCircle',      label: 'Failed' },
  expired:      { token: 'state-muted',   icon: 'MinusCircle',  label: 'Expired' },
} as const;

// [v3.0] The assurance ladder's six rungs — plus the only honest rendering of a missing signal.
export const assuranceTier = {
  attempted:   { level: 0, token: 'state-neutral', icon: 'Circle',       label: 'Attempted' },
  provider:    { level: 1, token: 'state-neutral', icon: 'ArrowUpRight', label: 'Provider accepted' },
  device:      { level: 2, token: 'state-info',    icon: 'Smartphone',   label: 'Device delivered' },
  opened:      { level: 3, token: 'state-info',    icon: 'Eye',          label: 'Opened' },
  acknowledged:{ level: 4, token: 'state-ok',      icon: 'CheckCircle2', label: 'Acknowledged' },
  responded:   { level: 5, token: 'state-ok',      icon: 'MessageSquare',label: 'Response received' },
  // Struck through, NOT greyed (reads as loading) and NOT hidden (reads as unchecked). Rule 8.
  notApplicable:{ level: null, token: 'state-muted', icon: 'Slash', label: 'Not applicable',
                  decoration: 'line-through' },
} as const;

// [v3.0] Governance states — the missing signature must be the loudest thing on screen (Part 0.5).
export const governance = {
  draft:           { token: 'state-muted',   icon: 'FileEdit',    label: 'Draft' },
  blocked:         { token: 'state-danger',  icon: 'ShieldAlert', label: 'Blocked by quality gate' },
  pendingApproval: { token: 'state-warning', icon: 'UserCheck',   label: 'Awaiting authorization' },
  approved:        { token: 'state-ok',      icon: 'ShieldCheck', label: 'Authorized' },
  superseded:      { token: 'state-muted',   icon: 'History',     label: 'Superseded' },
} as const;

// [v3.0] Provenance chips — same visual family as the existing SIM badge.
export const provenance = {
  simulated:    { label: 'SIM',   tooltip: 'Simulated carrier — flagged in the database' },
  humanRelay:   { label: 'HUMAN', tooltip: 'Confirmed by a person, not a digital receipt' },
  peerRelay:    { label: '⇄ PEER', tooltip: 'Received via a nearby device, signature verified' },
  bootstrapML:  { label: 'BOOTSTRAP', tooltip: 'Model trained on a published physical process, not outcomes' },
  authoritative:{ label: 'AUTO-AUTH', tooltip: 'Approved by an authoritative source, not a human' },
} as const;
```

```css
/* dark-first ops console */
:root[data-theme="dark"] {
  --bg-base: #0B0D10;  --bg-surface: #14171C;  --bg-raised: #1B1F26;
  --border-subtle: #262B33;
  --text-primary: #E8EBF0;   /* 14.8:1 on base  */
  --text-secondary: #9AA4B2; /*  6.1:1 on base  */

  --sev-extreme-bg: #3B0A0A;  --sev-extreme-fg: #FF6B6B;  /* 7.1:1 */
  --sev-severe-bg:  #3A2408;  --sev-severe-fg:  #FFA94D;  /* 8.4:1 */
  --sev-moderate-bg:#3A3408;  --sev-moderate-fg:#FFD43B;  /* 11.2:1 */
  --sev-minor-bg:   #0A2A3B;  --sev-minor-fg:   #4DABF7;  /* 6.9:1 */

  --state-ok: #51CF66;  --state-danger: #FF6B6B;
  --state-info: #4DABF7; --state-neutral: #868E96; --state-muted: #495057;
  --state-warning: #FFA94D;   /* [v3.0] pendingApproval — 8.4:1, same as sev-severe-fg */
}
```

**Every severity and state carries an icon and a text label, never colour alone** — a hard requirement for red/green colour-blind users on a life-safety tool. **[v3.0]** the same rule extends to every new token above: `notApplicable` has an icon (`Slash`), a label ("Not applicable"), *and* a text decoration — three independent channels, because this is the one state that must never be misread as "failed" or "loading."

**Density scale:** `4 / 8 / 12 / 16 / 24 / 32 px`. **Type:** Inter (UI) + **JetBrains Mono with `tabular-nums`** for every count, timestamp and duration — non-negotiable.

## 11.2 Console screens **[v3.0 — four new screens, one new component]**

| Screen | Contents |
|---|---|
| **Live Operations** | MapLibre choropleth ∥ virtualised status table. KPI strip: targeted / delivered / acknowledged / at-risk. WebSocket-driven. |
| **Alert Composer** | Polygon draw → exposure preview → severity → message → **[v3.0] quality-gate checklist inline** → dry-run diff → dispatch |
| **Alert Detail** | Timeline, per-channel funnel, escalation trace, SIM badges, full audit ledger with hash chain, **[v3.0] `<AssuranceLadder>` per delivery** |
| **Analytics** | Ack rate by district/channel/time; channel reliability; quarantine feed health; **[v3.0] lead-time percentiles + coverage** |
| **Methodology** | Every threshold, model card, metric, stated limitation — **[v3.0] plus the full channel-capability table** |
| **[v3.0] Incident Page** | The version chain (v3 ACTIVE / v2 SUPERSEDED / v1 SUPERSEDED), each with its `change_reason` and diff; approval trail; close-incident action |
| **[v3.0] Command Board** | The one-screen common operating picture. Built **last** (Day 10) because every tile reads from a feature built earlier. |
| **[v3.0] Assistance Queue** | Priority-ordered cases, each expandable to its `priority_factors` breakdown; assign-to-team; status advance |
| **[v3.0] Approval Panel** | Shown on any alert in `pending_approval`: who created it, who has approved, **what is still missing at full contrast** |

### **[v3.0] `<AssuranceLadder>` — the component that carries Rule 8**

```tsx
// web/console/src/components/AssuranceLadder.tsx
// Renders from the API's per-channel payload. NOTHING about channel abilities is
// hardcoded here — capability comes from channel_capability via /alerts/{id}/assurance.
export function AssuranceLadder({ delivery, capability }: Props) {
  const rungs = [
    { tier: 'provider',     supported: capability.supports_provider_accept },
    { tier: 'device',       supported: capability.supports_device_delivered },
    { tier: 'opened',       supported: capability.supports_opened },
    { tier: 'acknowledged', supported: capability.supports_acknowledgement },
  ] as const;

  return (
    <ol className="assurance-ladder" aria-label="Delivery assurance">
      {rungs.map(({ tier, supported }) => {
        if (!supported) {
          return (
            <li key={tier} className="rung rung--na">
              <Icon name={assuranceTier.notApplicable.icon} />
              <s>{assuranceTier[tier].label}</s>
              {/* The reason, verbatim from the database. This sentence is the product. */}
              <span className="rung__reason">{capability.not_applicable_reason}</span>
            </li>
          );
        }
        const reached = delivery.assurance_level >= assuranceTier[tier].level!;
        return (
          <li key={tier} className={reached ? 'rung rung--reached' : 'rung rung--pending'}>
            <Icon name={reached ? assuranceTier[tier].icon : 'Circle'} />
            <span>{assuranceTier[tier].label}</span>
            {reached && <time dateTime={delivery.events[tier]}>{fmt(delivery.events[tier])}</time>}
          </li>
        );
      })}
    </ol>
  );
}
```

**What the officer sees for an SMS delivery:**
```
DELIVERY ASSURANCE — SMS to +91••••••3421
  ✔ Provider accepted            14:32:04
  ✔ Device delivered             14:32:11   (carrier confirmation)
  ⊘ ̶O̶p̶e̶n̶e̶d̶  — Not applicable: no mobile carrier exposes SMS read
      receipts to the sender. This tier cannot be measured for SMS by
      anyone, including us.
  ○ Acknowledged                 —
```

That struck-through line with its reason is, in one component, the entire thesis of v3.0: **the platform is more credible for the things it refuses to claim than for the things it claims.**

## 11.3 Real-time table — the details that separate polish from prototype

- **Virtualised** (`@tanstack/react-virtual`) — 7,000 rows at 60 fps.
- **No layout shift on update:** fixed column widths, `tabular-nums`, `content-visibility: auto`.
- **Row state changes crossfade over 200 ms**, never snap.
- **`prefers-reduced-motion` respected** — transitions collapse to instant.
- **Optimistic UI is banned here.** Showing "acknowledged" before the server confirms would be a lie in exactly the place lies are most dangerous.
- **[v3.0] The ban extends to the assurance ladder and the approval panel.** A rung never renders as reached until its `delivery_event` row exists server-side; an approval checkbox never ticks until `alert_approval` has the row. **[v3.0]** And one addition: the assistance queue **may** reorder optimistically on assignment (a local sort is not a truth claim about the world), but a case's *status* never advances in the UI before the server confirms.

## 11.4 Citizen PWA — offline is the whole point

```ts
// web/citizen/src/sw.ts
registerRoute(({url}) => url.pathname.startsWith('/api/v1/alerts/active'),
  new NetworkFirst({
    cacheName: 'setu-alerts-v1',
    networkTimeoutSeconds: CFG.networkTimeoutSeconds,   // config, not a literal
    plugins: [new ExpirationPlugin({maxAgeSeconds: CFG.alertCacheMaxAgeSeconds})],
  }));

// Acknowledgements survive being offline — queued and replayed on reconnect
const ackQueue = new BackgroundSyncPlugin('setu-ack-queue', {
  maxRetentionTime: CFG.ackRetentionMinutes,
});
registerRoute(({url}) => url.pathname === '/api/v1/ack',
  new NetworkOnly({plugins: [ackQueue]}), 'POST');

// [v3.0] Three more queues, same mechanism — C6 responses, B8 receipts, B10 peer receipts.
// All three MUST survive offline; all three are POST-only and idempotency-keyed.
const responseQueue = new BackgroundSyncPlugin('setu-response-queue',
  { maxRetentionTime: CFG.ackRetentionMinutes });
registerRoute(({url}) => url.pathname === '/api/v1/response',
  new NetworkOnly({plugins: [responseQueue]}), 'POST');

const receiptQueue = new BackgroundSyncPlugin('setu-receipt-queue',
  { maxRetentionTime: CFG.receiptRetentionMinutes });
registerRoute(({url}) => /\/deliveries\/\d+\/receipt$/.test(url.pathname),
  new NetworkOnly({plugins: [receiptQueue]}), 'POST');

// [v3.0] The push handler is where B8's device_delivered signal is born.
self.addEventListener('push', (event) => {
  const data = event.data!.json();
  event.waitUntil((async () => {
    // Rule 11: verify before display, even for a server push.
    if (!await verifySignature(data)) return;
    await self.registration.showNotification(data.headline, { body: data.body, data });
    // Fire-and-forget receipt; if offline, BackgroundSync replays it later.
    fetch(`/api/v1/deliveries/${data.delivery_id}/receipt`,
          { method: 'POST', body: JSON.stringify({ event: 'push',
              receipt_nonce: data.receipt_nonce }) }).catch(() => {});
  })());
});
```

**Test matrix for the cable-pull moment:** Android Chrome ✅ primary · Desktop Chrome ✅ · **iOS Safari ⚠️ — historically the weakest PWA offline target. Test on the exact device you will present with, from Day 6, every day.** If iOS misbehaves, present on Android. Decide by Day 8.

**[v3.0] The matrix now has a second ⚠️ row, and it is the same device:** Web Bluetooth (B10) is **Chromium-only and absent on iOS Safari entirely**. This means the *same* decision — "present on Android" — now covers two features instead of one, which actually **simplifies** the Day-8 go/no-go: there is one device decision, not two. Recorded here so nobody re-litigates it on the 23rd.

## 11.5 **[v3.0] Citizen PWA — the C6 response flow, in full**

Two screens, three taps maximum, no typing required except for "Other".

```
┌──────────────────────────────┐      ┌──────────────────────────────┐
│  ⚠ EXTREME — FLOOD           │      │  What do you need?           │
│  Meppadi, Wayanad            │      │                              │
│  Evacuate to higher ground    │      │  ┌────────────────────────┐  │
│  now. Nearest shelter 1.4 km. │      │  │  🔴  I am TRAPPED      │  │
│                              │      │  └────────────────────────┘  │
│  ⇄ Received via nearby device │      │  ┌────────────────────────┐  │
│    signature verified         │      │  │  🏥  MEDICAL help      │  │
│                              │      │  └────────────────────────┘  │
│  ┌──────────┐  ┌───────────┐ │      │  ┌────────────────────────┐  │
│  │ I'M SAFE │  │ I NEED    │ │  →   │  │  🚫  CANNOT evacuate   │  │
│  │    ✓     │  │  HELP  ⚠  │ │      │  └────────────────────────┘  │
│  └──────────┘  └───────────┘ │      │  ┌────────────────────────┐  │
│                              │      │  │  …  Something else     │  │
│  Nearest shelter →            │      │  └────────────────────────┘  │
└──────────────────────────────┘      └──────────────────────────────┘
```

**Four design rules, each with a reason:**

1. **Both primary buttons are on the first screen, equally weighted.** "I need help" behind a menu is a design that assumes everyone is fine. A 44px-minimum touch target each (WCAG), side by side, no default selection.
2. **Location is requested at the moment it becomes useful, never before.** Tapping "Trapped" shows: *"Share your location so responders can find you?"* with `[Share location]` and `[Continue without]`. Declining still files the case — it just files it with unit-level geography instead of a point. The `CHECK` constraint in §5.8 makes the promise structural.
3. **It works fully offline.** A queued response shows *"Saved. Will send as soon as there is a signal."* with a pending chip — never a spinner, never a silent failure. The citizen must know their tap was recorded even when nothing can be transmitted.
4. **A citizen can change their answer.** Safe → Need Help is a **new row**, not an update. The queue sees the latest; the ledger keeps both. Someone who was safe at 14:32 and trapped at 14:51 is exactly the person the system must not lose track of.

---

# PART 12 — SECURITY & PRIVACY

| Concern | Control |
|---|---|
| **PII at rest** | Phone/email encrypted with `pgcrypto`; key from env, never committed. **[v3.0]** `phone_hash` is HMAC-with-pepper, not a bare hash (Trap 11) — a bare SHA-256 of a 10-digit mobile number is brute-forcible in seconds |
| **PII in logs** | Structured logger with a redaction filter; phone/email/token keys masked. **[v3.0]** `phone_hash` added to the redaction list — it is a stable pseudonymous identifier, i.e. still personal data |
| **PII in the repo** | `detect-secrets`/`gitleaks` pre-commit + CI gate; seed data uses generated numbers |
| **PII on screen** | Console shows unit-level aggregates by default; individual contacts require an explicit reveal, and the reveal is itself an audit event |
| **Auth** | JWT, short TTL, refresh rotation; RBAC enforced by FastAPI dependency, not in handlers |
| **Webhooks** | HMAC signature verification on every provider callback; unsigned → 401 |
| **Dispatch** | Requires officer role + idempotency key + confirmation dialog stating recipient count. **[v3.0]** plus a passing quality gate and a satisfied approval quorum |
| **Rate limiting** | Per-IP and per-token via Redis sliding window |
| **Transport** | HTTPS only, HSTS, strict CSP, `SameSite=Strict` cookies |
| **Data minimisation** | Citizens may register with **push token only** — no phone, no email required |

**Consent is modelled explicitly** (`recipient.consented_at`).

## 12.1 **[v3.0] Five new attack surfaces, each closed**

Every new feature that accepts input from outside the trust boundary is listed here with its control. This section exists because "we added seventeen features in a week" is exactly the sentence that precedes a security incident.

| # | Surface | The attack | Control |
|---|---|---|---|
| 1 | **B10 peer relay** — a payload reaches a citizen's screen without touching our server | Inject a fake evacuation order over Bluetooth, or replay a stale alert as current | **Ed25519 signature verified before render** (Rule 11); `expires_at` is inside the signed payload so a replayed old alert is rejected as expired; unverified payloads are **discarded silently and logged locally** — never shown, never toasted (a "suspicious alert blocked" toast is itself an attack surface for panic) |
| 2 | **B8 service-worker receipt** — a public POST that raises the platform's headline metric | Forge receipts for deliveries that never arrived, inflating reachability | **Single-use nonce** generated per delivery, delivered inside the FCM payload, checked server-side (§8.3); `delivery_id` alone is worthless. Rate-limited per IP |
| 3 | **E4 SMS keyword enrollment** — an inbound webhook that creates database rows | Enroll someone else's number; flood the recipient table | **Only the verified sender's own number** can be enrolled — Twilio authenticates `From`, so registering a third party is impossible by construction. HMAC-verified. Rate-limited per sender. `STOP` is honoured immediately and permanently (`opted_out_at`), TRAI-aligned |
| 4 | **E4 CSV import** — bulk write to `recipient` by an authenticated officer | A malformed or duplicated file corrupts the Reachability denominator; a CSV-injection payload (`=HYPERLINK(...)`) executes when the file is later exported and opened in Excel | `?dry_run=true` **required first** and enforced by the UI; idempotent via `phone_hash` (Trap 11); every cell is prefixed-escaped on **export**; per-import audit event records row counts, inserted, skipped, rejected — one number a judge can check against the score |
| 5 | **C6 free-text "Other"** | Stored XSS in the console; unbounded text as a storage-exhaustion vector on a 0.5 GB database | Length-capped in the Pydantic schema; **rendered as text, never as HTML**; the console's CSP forbids inline script regardless |

## 12.2 **[v3.0] Where the auditor's access stops, and why**

v2.1's Part 26 established that an auditor sees *proof the system behaved correctly*, never the PII the system protects. v3.0 adds a case that needs deciding explicitly, because it is genuinely a hard one:

**A `citizen_response` of `trapped` with a shared location is the most sensitive row in the entire database.** It states that a named-by-implication individual was in a life-threatening situation at a specific coordinate and time.

| Role | Access to a trapped-citizen location |
|---|---|
| **officer** (own district) | ✅ Full — this is the person dispatching help; withholding it would be indefensible |
| **state_admin** | ✅ Full |
| **auditor** | ⚠️ **Aggregate and unit-level only.** Sees *that* a trapped case existed, its priority, its response time, and whether it was resolved — **never the point geometry.** An RTI applicant needs to prove the state responded; they do not need a map of which houses had someone trapped in them |
| **citizen** | ✅ Their own response only |
| **relay_node** | ❌ **No access to individual responses at all.** A relay operator receives *"twelve households in your area could not be reached"* — a count and an area, never a list of names, numbers, or who asked for help |

**The relay_node row is the one to be proud of.** The obvious implementation hands the village volunteer a list of households to visit — and would leak, to a semi-trusted community member, exactly who in the village called for medical help. We hand them a count and an area instead. It is slightly less operationally efficient and very substantially more defensible, and it is the kind of trade-off a life-safety system should make on purpose rather than by accident.

## 12.3 **[v3.0] Consent versus life safety — the tension, resolved and written down**

v2.1's rule is absolute: `test_no_delivery_without_consent()` — a recipient with `consented_at IS NULL` is **never** enqueued. That is correct for individually-targeted channels and it creates a real reach gap. v3.0 does **not** weaken it. Instead it states the boundary precisely:

| Channel class | Consent required? | Reasoning |
|---|---|---|
| Individually-addressed (**push, SMS, email, IVR**) | **Yes, absolutely.** No exception, no severity override. | We hold this person's contact details. Using them without consent is the abuse that would rightly end the project. |
| **Non-addressed area broadcast** (siren/PA) | **No — it targets an area, not a person.** | A siren addresses a place. There is no personal data involved, nothing to consent to, and no identifiable recipient. |
| **B9 human relay** | **The relay operator consents (they are a registered node). The households do not need to** — a person knocking on a door is not processing personal data. | This is precisely why B9 closes the consent-reach gap that no digital channel can: it reaches the unconsented without violating anyone's consent. |

**This is the honest answer to "what about citizens who never signed up?"** — and it is a better answer than a consent-override switch would have been. The unconsented are reached by the two channels that do not need their data: a broadcast to their area, and a human at their door. Both are recorded in the ledger. Neither requires us to misuse a phone number we were never given.

---

# PART 13 — TESTING STRATEGY

| Layer | Scope | Target |
|---|---|---|
| **Unit** | State machine, escalation policy, CAP parser, scoring, **[v3.0] each quality-gate rule, priority formula, fatigue window, signature verify** | **100% branch coverage on `services/delivery/state_machine.py`** |
| **Property** (Hypothesis) | Invariants that must never break | 4 from v2.1 + **[v3.0] 5 new, below** |
| **Contract** | Every `ChannelAdapter` against a shared conformance suite | all adapters pass identically — **[v3.0] including `human_relay`, and the suite now asserts declared capabilities match `channel_capability`** |
| **Integration** | ingest → **govern** → target → deliver → **assure** → **respond** → **assist**, on ephemeral Postgres+Redis | full path < 45 s (**[v3.0]** raised from 30 s — the governance and response stages are real work) |
| **E2E** (Playwright) | Compose → validate → approve ×2 → dispatch → ack → respond → assign → report, plus **offline mode** | green in CI |
| **Load** (Locust) | 7,000 units, 50 concurrent WS clients, **[v3.0] against the pooled Neon URL** | p95 API < 400 ms |
| **Chaos** | Kill a worker mid-fan-out; drop Redis; expire a provider token; **[v3.0] duplicate + out-of-order provider webhooks; flush Redis and rebuild the assistance queue** | zero lost deliveries, zero corrupted ladders |

### The four property tests from v2.1 that protect us from embarrassment

```python
@given(transitions=st.lists(st.sampled_from(list(State))))
def test_illegal_transitions_always_raise(transitions):
    """No sequence of events can drive a delivery into an illegal state."""

@given(st.integers(min_value=1, max_value=10_000))
def test_ack_is_idempotent(n):
    """N acknowledgements produce exactly one acked_at and one audit event."""

def test_audit_chain_is_unbroken():
    """For every alert, hash[i] == sha256(hash[i-1] || canonical_json(payload[i]))."""

def test_no_delivery_without_consent():
    """A recipient with consented_at IS NULL is never enqueued. Ever."""
```

### **[v3.0] The five new property tests — one per way this release could lie**

```python
# 1. Rule 8 — the honesty invariant. If this fails, the product's central claim is false.
@given(channel=st.sampled_from(ALL_CHANNEL_CODES), tier=st.sampled_from(ALL_TIERS))
def test_no_channel_reports_unsupported_tier(channel, tier):
    """A channel may never emit a delivery_event for a tier its capability row says
       it cannot prove. Specifically: no SMS delivery ever gets notification_opened,
       and no siren delivery ever gets device_delivered."""

# 2. Rule 12 — Four-Eyes cannot be defeated by one person.
@given(clicks=st.integers(min_value=1, max_value=50))
def test_single_officer_cannot_satisfy_quorum(clicks):
    """One officer approving N times yields exactly ONE approval row and never
       satisfies a 2-approval quorum. Guards the UNIQUE (alert_id, approver_id) index."""

# 3. Webhooks arrive duplicated and out of order in the real world. Prove we survive it.
@given(events=st.lists(st.sampled_from(list(AssuranceEvent)), min_size=1, max_size=40))
def test_assurance_level_is_monotonic_under_any_arrival_order(events):
    """assurance_level() never decreases, never exceeds the channel's max supported
       tier, and produces the same final value regardless of arrival order or duplicates."""

# 4. Rule 11 — the peer-relay trust boundary.
@given(tamper=st.binary(min_size=1, max_size=64))
def test_tampered_relay_payload_is_never_accepted(tamper):
    """Any single-byte mutation of a signed alert fails verification and is discarded.
       A payload with no signature field at all is also discarded, not treated as legacy."""

# 5. Trap 11 — the dedupe key actually dedupes.
@given(n=st.integers(min_value=1, max_value=20))
def test_csv_import_is_idempotent(n):
    """Importing the same CSV N times yields exactly one recipient per unique phone.
       This test exists because pgp_sym_encrypt is randomized and the obvious
       UNIQUE (phone_enc) would silently never fire."""
```

**Test 5 is the one that would have saved a day of confused debugging.** It fails loudly on the naive implementation, which is exactly what a property test is for.

### **[v3.0] Two chaos tests specific to this release**

```python
async def test_duplicate_out_of_order_webhooks_leave_a_clean_ladder():
    """Fire Twilio's status callback 5× with statuses arriving reversed
       (delivered before queued). Assert: exactly one delivery_event row per tier,
       assurance_level correct, zero exceptions in the log."""

async def test_assistance_queue_rebuilds_after_redis_flush():
    """FLUSHALL mid-incident. Assert the queue rebuilds from Postgres with identical
       ordering, and that no assistance_case was lost — §6.4's stated guarantee, tested."""
```

### CI gates — the build goes red on any of these

```yaml
- run: ruff check services/ && mypy services/delivery services/ml services/governance services/response
- run: pytest tests/unit --cov=services/delivery --cov-fail-under=95
- run: pytest tests/property tests/contract tests/integration
- run: python scripts/check_no_hardcoding.py         # Rule 1, mechanically enforced
- run: python scripts/check_env_example.py           # Part 25 drift guard
- run: python scripts/check_channel_capability.py    # [v3.0] Rule 8 — code vs table agreement
- run: npx playwright test
```

```python
#!/usr/bin/env python3
"""scripts/check_channel_capability.py — [v3.0] Rule 8, mechanically enforced.

Fails the build if an adapter class's declared capability flags disagree with its
channel_capability row, or if a capability is false with no not_applicable_reason.
A drift between code and table is precisely how a channel starts silently claiming
a tier it cannot prove — which would make the product's central honesty claim false.
"""
import sys, asyncio
from services.delivery.channels import ALL_ADAPTERS
from services.db import connect

FLAGS = ("supports_provider_accept", "supports_device_delivered",
         "supports_opened", "supports_acknowledgement")

async def main() -> int:
    db, failures = await connect(), []
    rows = {r["code"]: r for r in await db.fetch(
        "SELECT c.code, cap.* FROM channel c JOIN channel_capability cap ON cap.channel_id=c.id")}
    for adapter in ALL_ADAPTERS:
        row = rows.get(adapter.code)
        if row is None:
            failures.append(f"{adapter.code}: adapter exists with no channel_capability row")
            continue
        for flag in FLAGS:
            if getattr(adapter, flag) != row[flag]:
                failures.append(f"{adapter.code}.{flag}: code={getattr(adapter, flag)} "
                                f"table={row[flag]} — they must agree")
        if not all(row[f] for f in FLAGS) and not row["not_applicable_reason"]:
            failures.append(f"{adapter.code}: a tier is unsupported but no "
                            f"not_applicable_reason is set — Rule 8 requires the reason, "
                            f"because the UI renders it verbatim to the officer")
    for f in failures:
        print(f"::error::{f}")
    return 1 if failures else 0

sys.exit(asyncio.run(main()))
```

**`check_no_hardcoding.py`'s guarded directories are extended in v3.0:**
```python
GUARDED_DIRS = ["services/delivery", "services/targeting",
                "services/governance", "services/response"]   # [v3.0] + the two new packages
```
Because the two most literal-prone new features — the priority formula and the fatigue window — live in `services/response` and `services/delivery/fatigue.py`, and a hardcoded `0.35` in a priority weight is exactly the kind of thing that survives review and then cannot be explained in Q&A.

---

# PART 14 — OBSERVABILITY

```python
logger.info("delivery.state_changed", extra={
    "alert_id": a.id, "delivery_id": d.id, "unit_id": u.id,
    "channel": ch.code, "from": frm, "to": to,
    "attempt": d.attempt, "simulated": d.simulated,
    "trace_id": ctx.trace_id,
})
```

**Metrics** (`prometheus-fastapi-instrumentator`): fan-out latency p50/p95/p99 · per-channel success rate · ack rate by unit · queue depth · Redis command count *(budget guard!)* · quarantine rate by source.

**[v3.0] Seven new metrics, each tied to a decision someone would actually make:**

| Metric | Why it exists |
|---|---|
| `assurance_tier_distribution{channel,tier}` | The single best early-warning signal for "a provider webhook stopped arriving." If `device_delivered` for SMS drops to zero while `provider_accepted` keeps climbing, Twilio's callback is broken, not the network |
| `alerts_blocked_by_quality_gate{rule_id}` | If one rule blocks constantly, either the rule is wrong or the composer UI is missing a field. Both are fixable; neither is visible without this |
| `approval_wait_seconds` p50/p95 | How long a life-safety alert sits waiting for a second human. If p95 is minutes, the governance layer is a safety feature; if it is tens of minutes, it is a hazard, and we would need to say so |
| `assistance_queue_depth{status}` and `assistance_time_to_assign_seconds` | The operational heartbeat of D11f — a queue that grows without assignments is the failure mode |
| `relay_confirmations_total` / `relay_unavailable_total{unit}` | `relay_unavailable` counts the villages where the last resort does not exist. This is a **preparedness** metric, not a debugging one |
| `peer_relay_signature_failures_total` | Should be zero. Anything above zero is either a bug or an attempt (Rule 11), and both need looking at |
| `enrollment_total{consent_source}` | Whether E4 is actually working, split by CSV vs SMS keyword |

**A `redis_commands_today` gauge with the 16,600/day budget as a reference line.** Running out of Upstash quota at 14:00 on the 24th would be an avoidable, humiliating failure. We watch it — and **[v3.0]** §1.4 re-derived the per-run cost, so the reference line is honest rather than inherited.

**Errors:** Sentry free tier, `beforeSend` strips PII — **[v3.0]** including `phone_hash`.

---

# PART 15 — CI/CD & ENVIRONMENTS

| Env | Where | Data |
|---|---|---|
| **local** | docker-compose: Postgres+PostGIS, Redis, MailHog | seeded fixtures |
| **ci** | GitHub Actions service containers | ephemeral |
| **demo** | Vercel (web) + Render (API) + **HF Spaces (ML, Part 22)** + Neon (DB) + Upstash (Redis) | frozen snapshot + live feeds |

**Scheduled workflows, all mandatory:**

```yaml
# keepalive.yml — Neon suspends after 5 min idle; Render cold-starts ~50 s.
on:
  schedule: [{cron: "*/10 * * * *"}]
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -sf "$API_URL/health" || exit 1
      - run: curl -sf "$HF_SPACE_URL/health" || exit 1        # Part 22
```

```yaml
# snapshot.yml — freeze demo fixtures nightly so the demo never depends on a live feed
on:
  schedule: [{cron: "0 20 * * *"}]
```

**[v3.0] The snapshot now has more to freeze, and this matters more than it sounds.** The demo's Command Board reads from D7f/D8f/D11f, whose numbers derive from delivery and response history. A snapshot that captured `alert` and `delivery` but not `delivery_event`, `citizen_response`, `assistance_case`, or `relay_confirmation` would produce a **Command Board full of zeroes** when run offline — the demo's centrepiece screen, blank, on stage.

```python
# scripts/snapshot.py — [v3.0] the export set, explicit and complete.
SNAPSHOT_TABLES = [
    # v2.1
    "admin_unit", "unit_features", "safe_zone", "recipient",
    "alert", "alert_translation", "delivery", "audit_event",
    "model_registry", "reach_prediction", "app_config",
    "alert_source", "channel", "escalation_policy",
    # v3.0 — every one of these is load-bearing for a demo screen
    "incident", "alert_approval", "alert_validation_result",
    "channel_capability",          # without this the assurance ladder renders nothing
    "delivery_event",              # without this every ladder is empty
    "citizen_response", "assistance_case",
    "relay_node", "relay_confirmation",
]
```
**Verification is a test, not a hope** (`tests/integration/test_snapshot_completeness.py`): load a snapshot into an empty database, render every console screen headless, and **assert no screen contains a zero-state where the source database had data.** Run in CI on every push. This is the specific test that prevents the worst possible Day-24 outcome — a beautiful board full of zeros.

**Cold-start mitigation on demo day:** keepalive cron *plus* a teammate loading the console 10 minutes before you present. Belt and braces.
---

# PART 16 — THE ROADMAP: DAY 4 → DAY 13

Six people. Named owners. Every phase has an exit gate with a **go/no-go decision**. **[v3.0] This is one schedule, not two** — base-spec Phase 2–5 work and the new operational-closure work are interleaved per day, per owner, because a teammate cannot follow two documents.

| Owner | Role | **[v3.0] additional surface** |
|---|---|---|
| **D1** | Ingestion — USGS/GDACS/thunderstorm adapters, CAP parser, composer | **F1 quality gate, F2 versioning, incident linker** |
| **D2** | Delivery engine — Redis, state machine, channels, audit | **B8 assurance ladder, B9 human relay, F4 fatigue** |
| **D3** | Targeting + console — PostGIS, exposure, live map & table | **D7f, D8f, D9f, D10f, D11f** (the five console features) |
| **D4** | ML — dedup, reach-risk, translation, (stretch) Copilot | **D12f explanation, D13f lead-time, assists D3** |
| **D5** | Citizen PWA — offline, ack, routes | **C6 structured response, B10 peer relay** |
| **D6** | Platform — auth, config, CI, deploy, reports, deck | **F3 dual auth, E4 enrollment, all migrations, snapshot completeness** |

### ⚠️ The load-balance problem, named before it bites

**D3 owns five of the seventeen new features.** That is the most unbalanced allocation in this document and it is a real risk, not a rounding error. Three mitigations, all of them decided now rather than improvised on Day 8:

1. **Four of D3's five are `T1` views** — D7f, D8f, D10f are SQL views plus a card each (§5.12 already wrote the SQL). The `T2` item is D9f/D11f.
2. **D4 is explicitly assigned as D3's pair from Day 7 onward.** D4's own new work (D12f, D13f) is two endpoints extending existing ones; the reach-risk and dedup work is largely done by then. **D4 builds D11f's assistance queue UI while D3 builds D9f's board.**
3. **D9f (Command Board) is scheduled last, on Day 10, and is the designated first cut.** See the cut-order list at the end of this part.

---

## 🚦 DAY 4 — Fri 14 Aug — **Foundations for the whole new layer, in one day**

**Goal:** every migration applied, every config row seeded, the assurance ladder writing real rows. **Nothing after today can start if the schema isn't there**, which is why all six migrations land today rather than incrementally.

### Base-spec Phase 2 work continuing today
- **D2:** full fan-out → FCM → delivery receipt → ack → audit chain; escalation policy driving retries
- **D3:** targeting engine with exposure preview; live map + virtualised table over WebSocket
- **D1:** manual composer with polygon draw + dry-run preview
- **D5:** offline caching working; ack queued offline and replayed on reconnect
- **D4:** dedup clustering with the spatial/temporal veto; begin hand-labelling ~200 alert pairs
- **D6:** deployed to Render + Vercel + Neon + Upstash; keepalive cron live

### **[v3.0] New work today**

| Task | Owner | Definition of Done |
|---|---|---|
| **Migrations `0007`–`0012`** applied in order (§5.13), each with a working down-revision | D6 | `alembic upgrade head` then `alembic downgrade 0006` then `upgrade head` again — all clean. `\dt` shows 8 new tables; `\dv` shows 3 new views |
| **`PHONE_HASH_PEPPER` + `ALERT_SIGNING_SEED_B64` generated**, added to `.env.example` (placeholders) and to Render/Vercel/HF env | D6 | `0012` backfill succeeds; `scripts/check_env_example.py` green. **Migration must FAIL LOUDLY if the pepper is absent** — verify by running it once with the var unset |
| **All `app_config` seeds** (Part 21) committed as `data/seeds/*.sql` and applied | D6 | `SELECT COUNT(*) FROM app_config` ≥ 74; every key in Part 21 present; every row has a non-empty `note` |
| **`channel_capability` seeded** (§8.2), including the `human_relay` and `community_relay` channel rows | D2 | 8 rows; `scripts/check_channel_capability.py` **runs and passes** in CI today, not later |
| **`assurance.record()` + `assurance_level()`**, wired into the FCM adapter's `send()` | D2 | Dispatch one real test alert → `SELECT * FROM delivery_event WHERE event_type='provider_accepted'` returns a row with a **real FCM message ID** in `evidence_id` |
| **F1 quality gate: 3 of 6 rules real** — `geometry_non_empty`, `expiry_set`, `target_count_plausible`; the other 3 registered but returning `pass` with an explicit `# Day 5` marker in the PR description | D1 | `pytest tests/unit/test_quality_gate.py` — an alert with no `expires_at` returns a `fail` row with `rule_id='expiry_set'`; `POST /alerts/{id}/validate` returns the per-rule list |
| **Incident backfill verified** — every pre-existing alert now belongs to a single-version incident | D1 | `SELECT COUNT(*) FROM alert WHERE incident_id IS NULL` returns **0** |

**Exit gate (21:00):**
- [ ] `alembic upgrade head` → `downgrade 0006` → `upgrade head` all clean on the dev database **and** on Neon
- [ ] One real, non-mock `provider_accepted` row exists with a real provider ID
- [ ] `check_channel_capability.py` and `check_env_example.py` both green in CI
- [ ] Zero alerts with a NULL `incident_id`
- [ ] **The base spec's existing Phase-2 work is not behind** — if it is, everything in the v3.0 column stops until it isn't

**If missed:** the migrations are **not** allowed to slip — every other new feature blocks on them. If the day runs long, cut the three deferred quality-gate rules (they're already stubbed) and D2's ladder wiring to Day 5 morning. **Do not cut the pepper/signing-key generation** — `0012` cannot backfill without the pepper, and re-running a backfill on a populated table on Day 7 is a much worse afternoon than generating a secret today.

---

## DAY 5 — Sat 15 Aug — **Governance becomes real; the ladder gets its provider signals**

| Task | Owner | Definition of Done |
|---|---|---|
| **F1 complete** — remaining 3 rules real: `escalation_policy_exists`, `translation_exists`, `target_area_plausible`; results persisted to `alert_validation_result`; composer renders the checklist inline | D1 + D3 | All 6 rules have a unit test with a passing and a failing fixture. A blocked alert shows the failing rule *adjacent to* the disabled dispatch button (Part 0.5), not as a dismissible toast |
| **F3 dual authorization** — `POST /alerts/{id}/approve`; dispatch guard; `provenance='authoritative_source'` auto-approval path for `is_authoritative` sources (Rule 12) | D6 | Scripted test: severe alert + 1 approval → **409** with `{"have":1,"need":2}`; + a 2nd *distinct* officer → dispatch succeeds; same officer twice → still 409 and **only one row** in `alert_approval`. A USGS-ingested minor alert dispatches with **zero** human steps |
| **B8 SMS + IVR webhooks** → `device_delivered` / DTMF, HMAC-verified, idempotent via `ON CONFLICT DO NOTHING` | D2 | A **real** SMS to a verified number produces a `device_delivered` row within 60 s of Twilio's callback. Firing the same callback 5× produces exactly **one** row |
| **B8 service-worker receipt** — nonce issued at send, `POST /deliveries/{id}/receipt`, `push` + `notificationclick` handlers | D5 | A real push to a real phone produces `device_delivered`; tapping it produces `notification_opened`. A forged POST with a wrong nonce returns **403** |
| **C6 structured response** — both PWA screens, `POST /api/v1/response` idempotent, consent-gated location, offline queue | D5 | Tap flow round-trips; one real `citizen_response` row; `CHECK` constraint proven by attempting an insert with a location and `location_consent=false` (must fail) |
| **D7f + D8f views exposed** — `/units/{id}/reachability`, `/units/{id}/vulnerability`; `<ReachabilityCard>` on the unit panel | D3 | `curl` against 5 seeded units returns non-null `population_reach_pct` **and** `recipient_reach_pct` for all 5, each labelled with `geometry_level` (§4.1) |
| **B6 IVR promoted to core** — outbound call + `<Gather>` + DTMF→C6 mapping (§8.4) | D2 | A real call to a verified number; pressing `2` then `1` creates a `citizen_response` of `trapped` |

**Exit gate (21:00):**
- [ ] Quality gate blocks a genuinely invalid alert, and the reason is on screen next to the disabled button
- [ ] Dual auth: 409 → dispatch, with two distinct officers; one officer cannot self-quorum
- [ ] A real SMS **and** a real push each produced a `device_delivered` row from a real provider signal
- [ ] Structured response round-trips end to end, including one offline-then-sync cycle
- [ ] `pytest tests/property/test_single_officer_cannot_satisfy_quorum.py` green

**If missed:** B6/IVR may slip to Day 6 (it is the newest promotion and has the most Twilio-configuration risk). **F3 cannot slip** — Day 6's versioning work and Day 9's integration run both depend on the approval path existing.

---

## DAY 6 — Sun 16 Aug — **Lifecycle, timeline, relay — and the base spec's GATE 3 (the cable test begins)**

Today carries the base spec's most important gate. **New work stops the moment Gate 3 is at risk.**

| Task | Owner | Definition of Done |
|---|---|---|
| **F2 versioning** — `POST /alerts/{id}/new-version`; `supersede()` with in-flight cancellation (§7.3); Redis supersede lock; Incident Page renders the version chain with `change_reason` | D1 + D3 | Draft v1 Moderate → escalate to v2 Severe → Incident Page shows **v2 ACTIVE / v1 SUPERSEDED**; `alert_one_active_per_incident_uix` proven by attempting two actives (must fail); pending v1 deliveries show `expired` with `reason='superseded_by_version'` |
| **D10f incident timeline** — `GET /incidents/{id}/timeline` over `audit_event` | D3 | One full test dispatch yields a timeline with **≥8 distinct event types** in correct chronological order, including `alert.validation_failed`, `alert.approved`, `delivery.assurance_advanced`, `citizen.response_received` |
| **D12f decision explanation** — `/units/{id}/risk` extended with `top_factors` + `recommended_action`, both derived from stored `reach_prediction.features` | D4 | Response for the Wayanad and Palghar units each lists **≥3 named factors** with values, plus the `is_bootstrap` disclosure string |
| **B9 human relay** — `HumanRelayAdapter`, `relay_node` seeds (§4.7), TwiML relay script (translated via C3), `relay_confirmation` write, `on_channels_exhausted` branch (§7.4) | D2 | A **real** call to a seeded relay node, DTMF `1` pressed → `relay_confirmation` row with `confirmed_by_human=true`. A unit with no active relay node produces a `relay.unavailable` audit event, **not** a silent no-op |
| **B10 peer relay — signing side** — `sign_alert()` server-side, signature in the FCM payload, `verify()` in the PWA, unverified payloads discarded + logged | D5 + D6 | `pytest tests/property/test_tampered_relay_payload_is_never_accepted.py` green; a real push arrives and the PWA logs `signature ok` before rendering |
| **Re-run base-spec GATE 3 with today's features active** | D5 + Presenter | Network unplugged → PWA shows the alert **and both C6 buttons**; tap "Need help → Trapped" offline; replug → the response syncs and appears in the console |

**Exit gate — base-spec GATE 3, unchanged, plus v3.0:**
- [ ] Compose → dispatch → real push on a real phone → tap ack → console turns green, **end to end**
- [ ] **Unplug the network. The citizen PWA still shows the alert.** *(From today, tested every single day.)*
- [ ] Audit chain verifies; `UPDATE audit_event` raises the trigger exception
- [ ] **[v3.0]** A relayed-by-human confirmation exists and renders with the `HUMAN` chip, visibly distinct from digital delivery (Rule 9)
- [ ] **[v3.0]** The version chain renders and a superseded version's in-flight deliveries are expired

**If missed:** B10's signing may slip to Day 7 — but **only the Bluetooth transport**, never the signature verification, because Day 7 builds the transport on top of it. If Gate 3 itself is at risk, **cut F2's in-flight cancellation** (keep the version chain, drop the cancellation) and re-attempt on Day 8.

---

## DAY 7 — Mon 17 Aug — **The response loop closes; enrollment opens**

Base-spec Phase 3 starts today: D4's reach-risk case-study validation (Wayanad/Palghar), D2's pre-emptive escalation + SMS/SIM badges, D3's analytics + Overpass safe-zone seeding, D6's audit report + methodology endpoint, D5's evacuation routing + accessibility pass. **D4 pairs with D3 from today** (see the load-balance note above).

| Task | Owner | Definition of Done |
|---|---|---|
| **D11f assistance queue — server** — `assistance_case` populated from every non-`safe` response; `compute_priority()` with `priority_factors` stored (Rule 10); Redis ZSET batch ordering (§6.4); `GET /assistance` | D3 | 10 seeded responses produce a queue whose order matches **hand-calculated scores for 3 spot-checked rows**; every row's `priority_factors` is non-NULL and contains all 5 factors + the weight set |
| **D11f assistance queue — UI** — priority-ordered list, each row expandable to its factor breakdown | **D4** | Clicking a case shows *"why is this first"* as a readable breakdown, not a bare number |
| **E4 CSV import** — `POST /admin/recipients/import` with **mandatory `?dry_run=true` first**, `phone_hash` dedupe, per-import audit event with counts, export-side CSV-injection escaping | D6 | Importing a 50-row CSV yields 50 consented recipients; **re-running the identical file yields 0 new rows**; `pytest tests/property/test_csv_import_is_idempotent.py` green |
| **E4 SMS keyword enrollment** — inbound webhook, `REGISTER` + `STOP`, rate-limited, HMAC-verified | D6 | A real `REGISTER` SMS from a verified number creates a recipient with `consent_source='sms_keyword'` and gets the auto-reply; `STOP` sets `opted_out_at` and the recipient is **never enqueued again** |
| **B10 peer relay — transport** — Web Bluetooth GATT service, chunked payload write, receipt queued offline (§8.7) | D5 | **On two physical Android devices:** device B in airplane mode receives and renders an alert relayed from device A, with the `⇄ PEER` provenance chip and the disclosure text |
| **D13f lead-time** — `estimated_onset_at` populated by GDACS + Open-Meteo + composer (NULL for USGS); `/analytics/lead-time` returning percentiles **and `coverage_pct`** | D4 | Endpoint returns p10/p50/p90 for forecast hazards and states its own coverage; a seismic alert is **excluded**, and the response says why |

**Exit gate (21:00):**
- [ ] The full response loop works: **a citizen taps "Trapped" → a prioritised, factor-explained case appears in the officer's queue**
- [ ] CSV import is provably idempotent; SMS `REGISTER`/`STOP` both work on a real handset
- [ ] Peer relay succeeds at least once between two real Android devices, with signature verification and the provenance chip
- [ ] Lead-time endpoint publishes its own coverage percentage

**If missed:** **B10 is the designated slip item** — it may move to Day 10 without consequence, because it is a standalone demo beat that touches nothing else. If two items must slip, the second is D13f (a `T1` view; half a day at any point).

---

## DAY 8 — Tue 18 Aug — **Fatigue, assignment, and the iOS/Android device decision**

| Task | Owner | Definition of Done |
|---|---|---|
| **F4 alert fatigue** — `is_fatigued()` + `build_message()` relabel; **never suppresses** | D2 | 3 related alerts to one recipient inside the configured window → the 3rd carries the config-driven `URGENT UPDATE — ` prefix; the 1st and 2nd do not. A test proves a 4th **extreme** alert is still delivered in full |
| **D11f assignment** — `PATCH /assistance/{id}`; status `new → assigned → en_route → assisted → closed`; `assigned_by` recorded; every transition an audit event | D4 | An officer moves one real case through all five statuses in the console; the `CHECK` constraints reject an assignment with no team and a close with no `resolved_at` |
| **🛑 DEVICE DECISION — iOS vs Android, final** | D5 + Presenter | **One decision, covering both weak spots** (offline PWA + Web Bluetooth, §11.4). Written into the team channel and into `docs/demo-device.md`. Not revisited after today |
| **D9f Command Board — data layer only** — `GET /incidents/{id}/board` returning one payload assembled from D7f/D8f/D11f/B8 | D3 | The endpoint returns real numbers for the test incident used on Days 6–7. **Zero hardcoded fields** — verified by `grep` for numeric literals in the router |
| **Snapshot completeness** — `SNAPSHOT_TABLES` extended (§15); `test_snapshot_completeness.py` in CI | D6 | Load a snapshot into an empty DB → **every console screen renders non-zero where the source had data.** This test is the one that prevents a blank Command Board on stage |
| **Re-run the offline test** with fatigue + assignment active | D5 | Same criteria as Day 6 |

**Exit gate (21:00):**
- [ ] Fatigue relabels a repeat and **provably never suppresses** an extreme alert
- [ ] A case moves through all five assistance statuses, each one audited
- [ ] **The device decision is made and written down**
- [ ] `test_snapshot_completeness.py` green in CI
- [ ] Offline test still green

**If missed:** F4 is [S] stretch — **cut it without discussion** if the day is tight. The device decision **cannot** slip; making it on the 23rd is how teams discover on stage that their money-shot doesn't run on the presenter's phone.

---

## DAY 9 — Wed 19 Aug — **BASE-SPEC GATE 4 + the full integration run**

**Today is the most important day in this document.** Base-spec Gate 4 and the v3.0 integration run must both pass, and the run is screen-recorded to become the fallback proof if anything regresses later.

| Task | Owner | Definition of Done |
|---|---|---|
| **THE FULL RUN, all hands, screen-recorded, one unbroken take** | All 6 | See the sequence below — every step observed, no step simulated except SMS to unverified numbers |
| **Regression: automated ingestion is not blocked by governance** | D1 | One live USGS-sourced minor alert dispatches with **zero manual approval steps**, `provenance='authoritative_source'` in `alert_approval`. Then one *manually composed* extreme alert **does** require two humans. Both verified in the same session |
| **Regression: base-spec state machine coverage** | D2 | `pytest --cov=services/delivery --cov-fail-under=95` still green after all v3.0 writers were added (Part 7's whole design point, verified) |

### The integration run, step by step — this is the acceptance test for the entire release

```
 1. A real GDACS or Open-Meteo event ingests            → incident opened, v1 drafted, cluster linked
 2. Officer A opens the composer, escalates severity     → v2 drafted, change_reason required & given
 3. Quality gate runs                                    → one rule deliberately failed, dispatch BLOCKED
 4. Officer A fixes the expiry, re-validates              → all 6 rules pass
 5. Officer A approves                                    → 1/2, dispatch returns 409
 6. Officer B (different login, different device) approves → 2/2, dispatch enabled
 7. Dispatch                                              → fan-out across fcm + sms + ivr + sim
 8. Assurance ladder fills in real time                   → provider_accepted → device_delivered
                                                             (real FCM receipt, real Twilio callback,
                                                              real answered IVR call)
 9. SMS's "opened" rung renders struck through            → with its not_applicable_reason verbatim
10. A real phone taps "I NEED HELP → TRAPPED"             → citizen_response + assistance_case
11. Assistance queue orders it first                      → priority_factors breakdown visible
12. Officer assigns it to a field team                    → status advances, audited
13. One unit exhausts every digital channel               → human_relay task created (§7.4)
14. A real relay call is answered, DTMF 1 pressed         → relay_confirmation, HUMAN chip, Rule 9 honoured
15. NETWORK UNPLUGGED                                     → PWA still shows the alert; tap Trapped offline
16. Device A shares to Device B over Bluetooth            → ⇄ PEER chip, signature verified, offline
17. NETWORK RESTORED                                      → both queued items sync; console updates
18. Incident Timeline                                     → every one of steps 1–17 present, in order
19. Command Board                                          → real reachability, vulnerability, queue depth
20. Audit ledger + live UPDATE attempt                    → Postgres trigger raises on screen
21. Methodology endpoint                                   → channel_capability table, live, in a browser tab
```

**Exit gate — base-spec GATE 4 **plus** the run:**
- [ ] Reach-risk model flags the real Wayanad and Palghar units as high-risk *(or we report honestly that it did not)*
- [ ] Dedup precision/recall measured on the held-out set and **written down**
- [ ] A real SMS arrives on a real phone in the room
- [ ] Audit report PDF generates for a real alert
- [ ] **[v3.0] All 21 steps above completed in one unbroken, recorded take**
- [ ] **[v3.0] Automated ingestion provably unaffected by the governance layer**
- [ ] **[v3.0] State-machine coverage still ≥95%**

**If missed:** this is the one day with **no slack**. If the run breaks at step N, fix and re-run the same day — do not proceed to Day 10 with a broken run, because Day 10 builds the Command Board on top of exactly this data. If a *single* step is unfixable, cut that step's feature from the demo entirely (see cut order) rather than showing a run with a known hole.

---

## DAY 10 — Thu 20 Aug — **Command Board, and the honest cut list**

| Task | Owner | Definition of Done |
|---|---|---|
| **D9f Command Board — UI** | D3 | Every tile real, every reachability figure labelled with its `geometry_level`, worst-3 units listed from D8f, queue depth from D11f, per-channel assurance from B8. `grep` for numeric literals in the component returns nothing |
| **D14f after-action *(stretch)*** — `GET /incidents/{id}/after-action`, every recommendation citing its measurement | D6 | For the Day-9 incident, produces ≥3 recommendations, each with the number it derives from. **Cut without guilt if the board is not finished** |
| **Config audit** — `check_no_hardcoding.py` against `services/governance/` and `services/response/` specifically | D6 | Green. **If it has never fired once during the whole build, treat that as suspicious, not as success** (Part 32's own rule) |
| **RBAC matrix tests** — one test per row of Part 26, including every new endpoint | D6 | Every row has an allow test and a deny test. The **relay_node** row is tested hardest: a relay-node token requesting `/assistance` gets 403 (§12.2) |
| **Accessibility pass on all four new screens** | D3 + D5 | axe-core clean; every new token pairing WCAG AA; `<AssuranceLadder>` reads correctly in a screen reader — the struck-through rung must announce as *"not applicable"*, not as blank |
| **B10 slip window closes** | D5 | If peer relay did not land on Day 7, today is the last day it may |

**Exit gate (21:00):**
- [ ] Command Board renders only real numbers, all tiles populated, from a **snapshot** as well as live
- [ ] `check_no_hardcoding.py` green on both new packages
- [ ] Every RBAC row has a passing allow **and** deny test
- [ ] All four new screens pass axe-core and the contrast gate

---

## 🛑 DAY 11 — Fri 21 Aug, 21:00 IST — **FEATURE FREEZE (base-spec GATE 5)**

| Task | Owner | Definition of Done |
|---|---|---|
| **`freeze-guard.yml` paths extended** to `services/governance/`, `services/response/`, `services/enrollment/`, `services/crypto/`, `web/citizen/src/relay.ts`, `web/console/src/pages/CommandBoard.tsx` | D6 | A deliberate test commit to one new path after the freeze timestamp is **blocked**, demonstrated once on purpose |
| **Full merged Definition of Done** (Part 19) walked line by line | All 6 | Every box ticked or explicitly waived with a reason in the team channel |
| **Final full snapshot committed** — with all 22 tables from §15 | D6 | `test_snapshot_completeness.py` green against the *final* snapshot, not an earlier one |
| **Nightly tag** | D6 | `git tag -a nightly-20260821` pushed — the known-good state to demo from |

**Exit gate:** after 21:00, commits require `[hotfix-approved]` and two teammates' agreement. **No new features. Not one.**

---

## PHASE 5 — DAYS 12–13 — Sat–Sun 22–23 Aug — **REHEARSAL**

| Task | Owner | Definition of Done |
|---|---|---|
| **Six full run-throughs**, network unplugged for the offline segment | Whole team, rotating | Every teammate can drive the whole demo alone |
| **The two-person choreography rehearsed as its own beat** | Officer A + Officer B | The dual-approval handoff (two logins, two devices) executed **10 times consecutively**; any fumble resets the count. This is the highest-risk *new* demo beat |
| **The Bluetooth beat rehearsed on the decided device, 10×** | D5 + Presenter | 10/10 successful relays. **If it fails even twice, it is cut from the live demo and shown from the recording instead** — decided in advance, not on stage |
| **Fresh-laptop test** | Any | `git clone && make demo`, timed |
| **Backup video recorded** — 3 minutes, includes the Bluetooth and dual-auth beats | D6 + Lead | Plays back offline, open in a second tab throughout |
| **Q&A drill** — Part 17.2's questions, out loud, until crisp | All | Including all six new v3.0 questions |
| **Load test against the pooled Neon URL** | D6 | 7,000 units, 50 WS clients, p95 < 400 ms |
| **Upstash counter check** | D2 | ≥5× headroom for demo day, per §1.4's revised arithmetic |
| **Adversarial pass** | Rotated | One person tries to break it; written "what a mean judge would ask" list with rehearsed answers |
| **Charge everything; HDMI + USB-C adapters; deck on a pen drive and emailed to all six** | D6 | Done |

---

## **[v3.0] THE CUT ORDER — decided now, in writing, so nobody negotiates at 1 a.m.**

If a day runs long, cut in **exactly this order**. The list is ordered by *lowest damage to the core thesis first*. It is the single most useful paragraph in this part.

| # | Cut | Why it's safe to lose |
|---|---|---|
| 1 | **D14f After-Action Intelligence** | [S] stretch, entirely post-incident, invisible in a 6-minute demo |
| 2 | **F4 Alert Fatigue Detection** | [S] stretch, a nice-to-have message tweak; nothing depends on it |
| 3 | **D13f Warning Lead-Time Analytics** | A `T1` view — real value, but it is a number on an analytics page, not a demo beat |
| 4 | **B10 Community Relay Mode** | The highest-drama beat, but **completely standalone** — nothing else references it. If the Bluetooth is flaky on the decided device, cutting it costs one slide, not a feature chain |
| 5 | **D9f Command Board (UI)** | The endpoint (Day 8) still exists and the individual screens (D7f/D8f/D10f/D11f) each show their own numbers. Losing the *rollup* is a presentation loss, not a capability loss |
| 6 | **E4 SMS-keyword enrollment** (keep CSV import) | CSV import alone still closes the enrollment story for the demo; the keyword flow is the more impressive half but the less load-bearing |
| 7 | **F2's in-flight cancellation** (keep the version chain) | The chain is the pitch; the cancellation is the correctness detail. Losing it is honest to disclose |

**Below this line, nothing may be cut** — these five are the release's thesis and each is a `T1` or a dependency of the integration run:

**B8 Delivery Assurance Ladder · B9 Trusted Human Relay · C6 Structured Emergency Response · F1 Quality Gate · F3 Dual Authorization · D7f Reachability Score.**

If those six cannot all ship, the correct response is **not** to cut one of them — it is to cut everything above the line and use the recovered days on these. A 4-minute demo of six rock-solid features beats six shaky minutes.

---

# PART 17 — DEMO SCRIPT & Q&A

## 17.1 The six-minute run **[v3.0 — rewritten]**

v2.1's script proved *delivery and audit*. v3.0's proves *the whole loop*. The hard constraint is that **six minutes cannot hold twenty-one integration steps** — so the script below picks seven beats and **the rest are visibly present on screen without being narrated**, which is a deliberate choice: a judge who notices an unmentioned `HUMAN` chip and asks about it has just handed you your best answer.

| Time | Beat |
|---|---|
| **0:00** | *"On 29 July 2024, an NGO warned a district office sixteen hours before the Wayanad landslide. 231 people died. The collector's office says it never received the warning. Someone had to file an RTI to ask what happened — and there is still no answer, because nobody was recording."* |
| **0:40** | *"India predicts disasters reasonably well. It fails in the last fifty kilometres. We built the layer that proves whether a warning arrived — and what happened next."* |
| **1:00** | **Compose and escalate.** Polygon over Wayanad. *"This incident already has a version one — a moderate warning from an hour ago. The forecast worsened."* Draft v2, severity Extreme. **The quality gate blocks it — no expiry set.** Fix it, re-validate, six green ticks. *"A wrong emergency message is worse than a late one."* |
| **1:40** | **Authorize.** *"Extreme severity, composed by a human. One human isn't enough."* Officer A approves — **dispatch returns 409, one of two.** Officer B approves on a second laptop. Dispatch unlocks. *"An earthquake from USGS doesn't wait for this — the seismograph is the second pair of eyes. A human-written extreme alert does."* |
| **2:20** | **Dispatch. The board fills.** A **real push lands on a phone held up to the judges. A real SMS arrives.** Dots go green. Some stay red. **Open one SMS delivery's assurance ladder:** provider ✓, carrier-confirmed device delivery ✓, **and "Opened" struck through with its reason.** *"No carrier on earth gives a sender an SMS read receipt. We could have shown you 88%. We show you what we can prove."* |
| **3:10** | **The citizen answers back.** On the held-up phone: **I NEED HELP → TRAPPED.** The case appears **top of the assistance queue** in the console. Expand it: five factors, five weights, a formula. *"Why is it first? Here's the arithmetic — not a black box."* Assign it to a field team. |
| **4:00** | **The village that went dark.** One unit exhausted push, SMS **and** IVR. *"This is Palghar. Every digital channel is gone."* The relay task fires — **a real phone in the room rings; the 'panchayat officer' presses 1.** A `HUMAN` chip appears in the ledger, next to — not merged with — the digital rows. *"That's a person, not a receipt. We store it separately, because conflating them would destroy the only thing this platform is for."* |
| **4:45** | **UNPLUG THE NETWORK.** Citizen PWA still shows the alert. Tap Trapped offline — *"Saved. Will send when there's a signal."* **Then tap "Share with someone nearby."** A second phone, in airplane mode, receives it — `⇄ PEER · signature verified`. *"Palghar's warning died with the cell towers. This one walks."* Replug — both sync, the dots turn. |
| **5:30** | **Timeline and ledger.** Every beat of the last five minutes, in order, hash-chained. Live `UPDATE audit_event` → **Postgres raises the exception on screen.** *"This is the answer the RTI never got."* |
| **5:50** | *"SACHET already tells a billion people a disaster is coming. It cannot tell you whether one of them heard it, whether anyone authorized it, or what happened to the person who couldn't get out. That's the gap. That's SETU."* |

**Visible but not narrated** (each is a gift to a curious judge): the Reachability Score card's two denominators; the Communication Vulnerability layer's `no_relay_coverage` units; the `BOOTSTRAP` badge on every risk score; the `SIM` badges; the version chain in the breadcrumb; the methodology endpoint open in a second browser tab.

## 17.2 The hard questions — rehearse out loud

**"SACHET already exists. What's new?"**
> We checked SACHET's platform directly. It publishes and pushes — SMS, app, browser, RSS, geo-targeted, 12 languages. What we could find no evidence of is per-recipient acknowledgement, retry-on-failure, or an audit trail. And critically, neither Wayanad nor Palghar failed at the national-broadcast layer — they failed in the human handoff below it, NGO to district to village officer. That layer has no instrumentation at all. We're the layer underneath, not a competitor above. To be straight with you: we could only inspect SACHET's public citizen-facing surface, not any internal official console.

**"Your SMS is simulated."**
> Partly, and deliberately. Three numbers in this room are real — you just saw one arrive. Nationwide SMS in India requires TRAI DLT registration, which needs a registered legal entity and about ten business days. That's the same regulatory path SACHET itself uses. Every simulated delivery is flagged `simulated=true` in our database and badged SIM on screen. The delivery engine, state machine, retry and escalation are identical on both paths.

**"Where did your ML training data come from?"**
> The dedup model is trained and evaluated on real CAP alerts we collected — here's precision and recall on a held-out split. The reach-risk model is a **bootstrap** model, and we say so in the UI. It can't be trained on historical acknowledgement outcomes because no system has ever recorded them — that's the very gap we're filling. So we trained on a published physical failure process using real terrain, tower and rainfall features, and validated it as a case study against Wayanad and Palghar. n equals two. **And this release is the part people miss: the assurance ladder and the structured responses are the instrument that finally collects that data. We didn't build a better model this week. We built the thing that will make one possible.**

**"What if the network fails during judging?"**
> It doesn't matter — and we'd like to show you. *(unplug)*

**"How do we know the audit log wasn't edited?"**
> Two ways. It's hash-chained — each row commits to the previous. And immutability is enforced by a Postgres trigger, not by our code. *(runs an UPDATE, exception appears)*

**"Why isn't your alert source SACHET or IMD?"**
> They're in the plan, registered for, and wired in behind the same adapter interface as everything else — but nothing depends on either being approved in time. Live ingestion runs on USGS and GDACS: zero auth, live today, covering earthquakes, cyclones, floods, wildfires and droughts for India. We added a third source ourselves — a thunderstorm nowcast on live Open-Meteo atmospheric data. If SACHET or IMD clear, they slot in as a fourth and fifth with a single database insert.

### **[v3.0] Six new questions, and the answers**

**"Your dual-approval gate delays an emergency alert. Isn't that dangerous?"**
> It would be, if it applied to everything — so it doesn't. The rule is: **human origin needs human approval; machine origin records machine provenance.** A USGS earthquake or a GDACS cyclone dispatches with zero human steps, because a seismograph network *is* an authority. A *human-composed* extreme alert needs a second human, because the failure mode there isn't delay — it's a wrong extreme alert sent to a district, which is also a harm, and one that destroys public trust in every future alert. We also measure the cost: `approval_wait_seconds`, p50 and p95, on our own dashboard. If that number were minutes, we'd tell you.

**"Your own thunderstorm model generates alerts. Does it approve its own?"**
> No — and that's the answer I'd most like you to remember. Our classifier is flagged `is_authoritative = false` in the source registry, because it's *our* bootstrap model, not an external authority. A severe thunderstorm alert from our own model needs two humans, same as one a person typed. A governance layer that exempts its owner's code isn't a governance layer.

**"'Not applicable' looks like something you didn't finish."**
> It's the opposite, and it's the single most deliberate design decision in the product. We could show you 88% and you'd have no way to check it. Instead: no mobile carrier anywhere exposes SMS read receipts to a sender — so for SMS, that tier can't be measured by us or by anyone. The reason is a column in our database, rendered verbatim to the officer, and published on our methodology endpoint. **We even declined a signal we could have faked: email open-tracking pixels. They're a privacy intrusion, they're blocked by most clients, and a blocked pixel is indistinguishable from an unopened email — so the number would have been invasive *and* wrong.**

**"Bluetooth relay — isn't that a way to inject fake evacuation orders?"**
> It would be without signatures, so every alert is Ed25519-signed server-side and the receiving device verifies against a public key baked into the app **before anything renders**. Expiry is inside the signed payload, so a replayed old alert fails as expired. An unverified payload is discarded silently and logged locally — we don't even toast it, because "suspicious alert blocked" is its own panic vector. And two honest limits: it's Chromium-only, so not iOS Safari; and it's **one hop, citizen-initiated by a tap** — browsers can't do background BLE scanning, so "automatic mesh" isn't a thing we could have built even with more time. We call it peer relay, not mesh, for that reason.

**"You hand a village volunteer a list of who needs help?"**
> No, and this is where we spent real design effort. A relay operator gets a **count and an area** — *"twelve households in your ward could not be reached"* — never names, numbers, or who asked for medical help. The obvious implementation hands them a list, and it would leak, to a semi-trusted community member, exactly who in the village called for help. Our auditor role is restricted the same way: an auditor sees *that* a trapped case existed and how fast it was resolved, never its point location. Slightly less efficient, substantially more defensible.

**"Biggest weakness?"**
> Two, and I'll give you the honest version of both. **Enrollment.** Every reach number we show you divides by the people who are registered, which is why the Reachability Score deliberately shows a *second* denominator — the unit's estimated population from WorldPop — so you can see the gap rather than us hiding it. CSV import and SMS keyword registration are real and shipping; a national telecom-scale enrollment needs DLT registration and a legal entity, which we don't have. **And geometry:** village-level polygons nationwide are a gigabyte, which doesn't fit a free database, so we target sub-district resolution nationally and village resolution only in Kerala and Maharashtra. That's a hosting cost, not a technical barrier, and we'd rather tell you than have you find it.

---

# PART 18 — RISK REGISTER

| # | Risk | P | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| 1 | SACHET discovery endpoint never found | Med | **Low** — A7 is stretch; A1/A2 satisfy Module A | Pursue, wire in if found | D1 |
| 2 | IMD registration not approved in time | Med | **Low** — same reasoning | Registered anyway; Open-Meteo covers rainfall | D1 |
| 3 | Upstash 500K/month exhausted | Med | **Fatal on the day** | Batched ops (§6.2, §6.4); **§1.4's re-derived per-run cost**; 80% webhook alert; local Redis for all dev | D2 |
| 4 | iOS Safari breaks the offline demo | Med | **High — it's the money shot** | Test daily from Day 6; **Day-8 device decision now covers both this and #15** | D5 |
| 5 | Render cold start on stage | Med | Moderate | Keepalive cron + manual pre-warm 10 min prior | D6 |
| 6 | Neon 0.5 GB exceeded by geometry | Med | High | ADM3 nationwide only; ADM5 for 2 states; configurable tolerance | D3 |
| 7 | DEM: no India tile in GLO-30's released set | Low | Low | Four-tile check (Part 29); SRTM per-cell fallback; then drop the feature — never fake it | D4 |
| 8 | Twilio trial expires or number unverified | Med | **Moderate → High in v3.0** | **Raised:** v3.0 has **five** Twilio consumers (SMS out, SMS status, IVR out, IVR inbound/DTMF, relay calls) against a finite trial **credit** — and two of them are per-minute **voice** (Trap 13). Create the account ≈18 Aug; verify demo phones ≥3 days early; **Part 28's send-counter check is now mandatory before every test from Day 18** | D2 |
| 9 | Scope creep past freeze | **High** | Severe | Gate 5 absolute; `freeze-guard.yml` extended to all new paths; **and Part 16's written cut order removes the 1 a.m. negotiation** | All |
| 10 | Laptop/projector failure | Low | Fatal | Recorded 3-min video (now including the dual-auth and Bluetooth beats); deck on pen drive + emailed | D6 |
| 11 | IndicTrans2 1B fails on CPU-only host | — | — | **Resolved** — 200M distilled variant (Trap 10) | D4 |
| 12 | Thunderstorm coverage missing | — | — | **Resolved** — Open-Meteo + Model 5 (Trap 8) | D4 |
| 13 | Evacuation-route data source missing | — | — | **Resolved** — OSM Overpass (Trap 9) | D5 |
| 14 | NDMA SOP documents not downloadable | Med | Low ([S] feature) | Part 31's concrete fallback corpus | D4 |
| **15** | **[v3.0] Web Bluetooth unsupported on the presenting device** | Med | Moderate | Same root cause as #4 → **one Day-8 decision covers both.** B10 is cut-order #4 and standalone; if 10 rehearsals aren't 10/10, it shows from the recording | D5 |
| **16** | **[v3.0] Dual-approval demo choreography fails live** (wrong login, wrong device, second laptop asleep) | **Med** | **High — it's a narrated beat** | Rehearsed as its own beat, 10× consecutive, from Day 12. Second laptop's session pre-warmed at T-10. **Fallback line rehearsed:** *"the second approval is on my colleague's laptop — here's the 409 our API returned, and here's the approval row"* — the API response alone proves the feature | D6 |
| **17** | **[v3.0] D3 overloaded — owns 5 of 17 new features** | **High** | Moderate | D4 paired to D3 from Day 7 and **owns the D11f UI outright**; 3 of D3's 5 are pre-written SQL views (§5.12); D9f is cut-order #5 | Lead |
| **18** | **[v3.0] `not_applicable` misread as "unfinished" by a judge** | Med | Moderate | Part 0.5's struck-through-with-reason rendering; **one rehearsed sentence** (17.2); the reason is a database column, not UI copy, so it survives into the methodology endpoint and the PDF report | Presenter |
| **19** | **[v3.0] Migration `0012` backfill fails on Neon** (pepper absent, or a populated `recipient` table) | Med | **High — blocks E4, D7f denominators** | Fails **loudly** by design (§5.13); run it on Day 4 while `recipient` is still small; down-revision tested the same day | D6 |
| **22** | **[v3.0] Hosted basemap tiles blank the live map during the unplugged beat** | **Was High, now closed** | **Severe — it is the centrepiece screen** | Self-hosted `.pmtiles` file (§1.6.5), `map.tile_source=pmtiles_local` asserted by the Day-11 snapshot check | D3 |
| **23** | **[v3.0] Twilio trial credit exhausted by voice rehearsals before demo day** | Med | High — B6 and B9 are both narrated beats | Trap 13's three mitigations: rehearse on the simulated adapter by default, credit check before every real call from Day 18, **and never top up** — a beat that needs money runs from the recording | D2 |
| **20** | **[v3.0] Snapshot missing the new tables → blank Command Board on stage** | Med | **High** | `SNAPSHOT_TABLES` explicit (§15); `test_snapshot_completeness.py` in CI from Day 8, asserted against the **final** snapshot on Day 11 | D6 |
| **21** | **[v3.0] Seventeen features in seven days degrades the base spec** | **High** | **Severe** | The base spec's gates are **unchanged and still binding** (Gate 3 re-run daily, Gate 4 unchanged, 95% state-machine coverage re-verified Day 9). Part 7 explains why the state machine was deliberately not touched. **The Day-4 exit gate explicitly states: if base-spec Phase-2 work is behind, all v3.0 work stops** | Lead |

## The three rules that decide hackathons

1. **Gate 1 is real, even without a STOP branch.** Verify load-bearing dependencies before you build on them, on Day 1 — not Day 9. None of SETU's core dependencies are still unverified, and **[v3.0] Rule 13 is why that stayed true through a 17-feature addition: nothing new needed a new dependency.**
2. **Feature freeze on 21 August is real.** The projects that lose are almost never the ones that built too little — they're the ones still adding features at 2 a.m., demoing something they never rehearsed.
3. **[v3.0] A written cut order beats willpower.** Risk #9 is rated High/Severe in every version of this document. The difference in v3.0 is that Part 16 names the seven things to cut, in order, *before* anyone is tired. Deciding what to abandon while rested is the whole trick.

---

# PART 19 — DEFINITION OF DONE

Everything in v2.0's Part 19 and v2.1's Part 33 still applies. **The full merged list:**

### From v2.0/v2.1 — unchanged, still binding
- [ ] `git clone && make demo` works on a fresh laptop
- [ ] The citizen PWA displays an alert and accepts an acknowledgement **with the network cable unplugged**
- [ ] A real push notification and a real SMS arrive on real phones during the demo
- [ ] Every simulated delivery is flagged in the DB **and** visibly badged in the UI
- [ ] The audit chain verifies, and `UPDATE audit_event` raises an exception live
- [ ] Dedup precision/recall measured on a held-out set and published in the UI
- [ ] Reach-risk model carries a visible **bootstrap** badge and its `disclosure` text
- [ ] `/api/v1/methodology` returns every threshold, metric and limitation
- [ ] `check_no_hardcoding.py` passes in CI
- [ ] **Branch coverage ≥ 95% on the delivery state machine — re-verified after every v3.0 writer was added**
- [ ] All six teammates can run the entire demo alone
- [ ] Redis command budget has ≥ 5× headroom for demo day
- [ ] USGS/GDACS ingestion runs with zero registration, zero auth, confirmed live
- [ ] Thunderstorm nowcast produces a risk score from live Open-Meteo data for a real India district
- [ ] Citizen PWA resolves a nearest safe zone from real OSM-sourced rows, not a hardcoded coordinate
- [ ] Translation runs on the 200M model on the actual free-tier host, not just locally
- [ ] `app_config` and extended `escalation_policy` seeded — every threshold is a row, not a comment
- [ ] `services/ml` runs as its own HF Space; `services/api` has zero `torch`/`transformers` imports
- [ ] App connects to Neon via the **pooled** URL; migrations use the **direct** URL
- [ ] Retry backoff shows visible growth + jitter in a captured log from a forced-failure test
- [ ] `.env.example` and the Part 25 table match exactly; CI fails if they drift
- [ ] The RBAC matrix is a table in the repo and every row has a test
- [ ] `freeze-guard.yml` is live and its block demonstrated once, deliberately
- [ ] The redis-budget and health-check webhook pings have each fired at least once
- [ ] The four-tile DEM check has a committed, dated pass/fail log
- [ ] Total spend: **₹0**

### **[v3.0] Added — the seventeen features, and the six ways they could have lied**

**Structural**
- [ ] Migrations `0007`–`0012` applied, **and every down-revision tested**
- [ ] Every new table has **at least one real, non-mock row** by its day's exit gate
- [ ] Every new threshold is an `app_config` row **with a non-empty `note`** explaining why that value
- [ ] `check_no_hardcoding.py` green on `services/governance/` and `services/response/` **specifically**
- [ ] `check_channel_capability.py` green — declared adapter flags match the database table
- [ ] All five new property tests green (Part 13)
- [ ] Both new chaos tests green (duplicate/out-of-order webhooks; Redis flush + queue rebuild)
- [ ] `test_snapshot_completeness.py` green **against the final Day-11 snapshot**

**Honesty — each of these is a way the release could have lied**
- [ ] **No channel reports a tier it cannot prove.** Verified by reading the *rendered UI*, not just the code: SMS's "Opened" rung is **struck through with its reason visible**
- [ ] **Human relay confirmations are visibly distinct** from digital delivery — the `HUMAN` chip, in the UI and in the PDF report
- [ ] **A relayed alert shows `⇄ PEER · signature verified`** plus the "peer relay, not mesh, one hop" disclosure
- [ ] **Reachability Score shows both denominators**, each labelled with its `geometry_level`
- [ ] **Lead-time analytics publishes its own `coverage_pct`** and excludes seismic alerts with a stated reason
- [ ] **Every assistance case's `priority_factors` is non-NULL** and its breakdown renders on screen
- [ ] **The Command Board contains zero hardcoded values** — verified by `grep` for numeric literals in the component

**Behavioural**
- [ ] The quality gate **blocks a genuinely invalid alert live**, with the reason adjacent to the disabled button
- [ ] Dual authorization demonstrated with **two distinct real logins on two devices**; one officer provably cannot self-quorum
- [ ] **An authoritative-source alert dispatches with zero human approval steps**, and a human-composed extreme one does not
- [ ] A superseded version's **in-flight deliveries expire** with `reason='superseded_by_version'`
- [ ] Fatigue detection relabels a repeat and **provably never suppresses** an extreme alert
- [ ] CSV import is **provably idempotent** on a second identical run
- [ ] `STOP` sets `opted_out_at` and that recipient is **never enqueued again**
- [ ] A `relay.unavailable` audit event exists for at least one unit with no relay coverage — **the platform can name where its last resort is missing**
- [ ] A relay-node token requesting `/assistance` gets **403** (§12.2)
- [ ] The base spec's **Gate 3 offline test passes with every new feature active**, re-confirmed on Day 11
- [ ] The **21-step integration run** completed in one unbroken recorded take (Day 9)
- [ ] The **two-person approval choreography** rehearsed 10× consecutively
- [ ] The **device decision** (iOS vs Android) is written into `docs/demo-device.md` and was not revisited after Day 8

**Part 38 — the two audits**
- [ ] All five Part 38.1 hardcoding violations are fixed in code, and `check_no_hardcoding.py` runs **all three passes** (Python AST · SQL · TS) plus the TwiML no-literals test
- [ ] `verify_seeds.py` asserts 74 `app_config` rows and 8 `channel_capability` rows before anything starts
- [ ] **The basemap renders with the network unplugged** — `.pmtiles` file present, `map.tile_source=pmtiles_local`, verified during a Gate-3 run, not assumed
- [ ] **Twilio trial credit has ≥2 real voice calls and ≥5 SMS remaining at T-30 min** — and B6/B9 have each been rehearsed on the simulated adapter so the demo survives credit exhaustion
- [ ] **Class ⑤ (fabricated) is empty** — walked screen by screen on Day 11: every rendered figure is measured, derived-with-stored-inputs, seeded-and-published, or badged
---

# PART 20 — THE LOOSE-END INVENTORY

## 20.1 v2.1's twelve loose ends — all closed, status carried forward

| # | Loose end | Closed in |
|---|---|---|
| 1 | "Loaded from config" said ~15 times with no actual default values | Part 21 |
| 2 | ML microservice hosts two transformers; Render free RAM cannot hold both plus PyTorch | Part 22 |
| 3 | Neon connection behaviour under a WebSocket console + concurrent pollers never addressed | Part 23 |
| 4 | `wait_before_next_s` flat — no backoff growth, no jitter | Part 24 |
| 5 | No enumerated list of every secret/env var | Part 25 |
| 6 | Four roles named, no endpoint-by-endpoint permission table | Part 26 |
| 7 | "Feature freeze" is a rule, not a mechanism | Part 27 |
| 8 | Monitoring dashboards with no threshold that triggers action | Part 28 |
| 9 | DEM risk scoped to "an India tile" — far broader than the four tiles actually needed | Part 29 |
| 10 | OpenCelliD token approval had no fallback | Part 30 |
| 11 | NDMA fetch failure never retried; no concrete mirror list | Part 31 |
| 12 | `check_no_hardcoding.py` referenced by name, never by content | Part 32 |

## 20.2 **[v3.0] Seven new loose ends this release created — and where each is closed**

A 17-feature addition creates its own loose ends. Naming them is the point of this section; every row is closed inside this document, not deferred to a v3.1 nobody will write.

| # | Loose end this release introduced | Why it would have bitten | Closed in |
|---|---|---|---|
| 1 | **Assurance ladder tiers vs. the existing 8-state `delivery_state` enum** — two overlapping vocabularies for "what happened to this delivery" | A naive merge would have rewritten the one module with a 95% coverage floor and four property tests, mid-build | **Part 7**: the state machine is deliberately untouched; `delivery_event` is an additive evidence log with a property test guarding the seam |
| 2 | **`pgp_sym_encrypt` is randomized, so `UNIQUE (phone_enc)` never fires** | A second CSV import silently doubles every recipient, corrupting the Reachability denominator — the pitch's headline metric | **Trap 11** + `phone_hash` HMAC column + migration `0012` + property test 5 |
| 3 | **Web Bluetooth cannot scan in the background or without a user gesture** | The whole feature would have been specified as "automatic mesh" and discovered impossible on Day 7 | **Trap 12**: re-specified as one-tap citizen-initiated peer relay; pitch language corrected everywhere |
| 4 | **FCM does not report device delivery to the sender** | The ladder's most-used tier would have been permanently empty for the primary channel, or worse, faked | **§1.2 + §8.3**: our own service-worker callback, nonce-protected |
| 5 | **Dual authorization would block automated USGS/GDACS dispatch** | An earthquake alert waiting for a human to wake up — a genuine safety regression introduced by a governance feature | **Rule 12** + `alert_source.is_authoritative` + `approval_provenance`; Day-9 regression test |
| 6 | **The snapshot didn't include the new tables** | The Command Board — the demo's centrepiece — renders entirely zeroes when run offline | **§15**: explicit `SNAPSHOT_TABLES` + `test_snapshot_completeness.py` in CI |
| 7 | **B10 creates a path where a payload reaches a citizen without touching our server** | Fake evacuation orders injectable over Bluetooth; replay of stale alerts as current | **Rule 11** + Ed25519 signing + `expires_at` inside the signed payload + property test 4 |

**Two more were found and are honestly *not* fully closed** — recorded here rather than hidden:

| # | Open item | Status |
|---|---|---|
| 8 | **D3 owns 5 of 17 new features** | Mitigated, not eliminated — Risk #17, D4 paired from Day 7, D9f is cut-order #5. Mitigation is a plan, not a guarantee |
| 9 | **Twilio trial now has five consumers against a 100-message cap** | Mitigated by Part 28's mandatory pre-send counter check from Day 18 and by creating the account late (≈18 Aug). If the trial runs dry mid-rehearsal, the `SimulatedCarrierAdapter` covers everything except the "real SMS in the room" beat — which is why that beat uses exactly one message |

---

# PART 21 — CONCRETE CONFIG: ACTUAL SEED VALUES, NOT THE WORD "CONFIG"

Run the migration first, then the seeds. This is `data/seeds/*.sql`, committed, applied on Day 4.

```sql
CREATE TABLE app_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    unit  TEXT,
    note  TEXT
);
ALTER TABLE escalation_policy ADD COLUMN backoff_multiplier NUMERIC NOT NULL DEFAULT 1.0;
ALTER TABLE escalation_policy ADD COLUMN jitter_ms INTEGER NOT NULL DEFAULT 0;
ALTER TABLE escalation_policy ADD COLUMN max_wait_s INTEGER;
```

## 21.1 Channels and escalation policy (v2.1, + two new channels)

```sql
-- channel_id mapping: 1=fcm 2=email 3=sms 4=ivr 5=siren 6=sim 7=human_relay 8=community_relay
INSERT INTO channel (code, class_path, config, cost_weight) VALUES
  ('fcm',   'services.delivery.channels.fcm.FcmAdapter',           '{}'::jsonb, 0),
  ('email', 'services.delivery.channels.email.BrevoAdapter',       '{}'::jsonb, 0),
  ('sms',   'services.delivery.channels.sms.TwilioSmsAdapter',     '{}'::jsonb, 5),
  ('ivr',   'services.delivery.channels.ivr.TwilioIvrAdapter',     '{}'::jsonb, 8),
  ('siren', 'services.delivery.channels.siren.WebhookSirenAdapter','{}'::jsonb, 1),
  ('sim',   'services.delivery.channels.simulated.SimulatedCarrierAdapter', '{}'::jsonb, 0),
  -- [v3.0]
  ('human_relay',     'services.delivery.channels.human_relay.HumanRelayAdapter', '{}'::jsonb, 12),
  ('community_relay', 'services.delivery.channels.community_relay.PeerRelayAdapter','{}'::jsonb, 0);

-- EXTREME: skip straight to push, escalate fast, exhaust every channel — then a human (§7.4)
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte) VALUES
  ('extreme', 1, 1, 90,  1.5, 5000, 2, NULL),   -- fcm
  ('extreme', 2, 3, 60,  1.5, 5000, 2, NULL),   -- sms: fast, extreme = life safety
  ('extreme', 3, 4, 45,  1.0, 2000, 1, NULL),   -- ivr: single attempt, voice IS the escalation
  ('extreme', 4, 5, 0,   1.0, 0,    1, NULL),   -- siren: immediate, no retry (physical)
  ('extreme', 5, 7, 120, 1.0, 0,    2, NULL);   -- [v3.0] human_relay: LAST resort, 2 attempts

-- EXTREME + high predicted reach-risk: skip fcm, go straight to sms (the Palghar fix, §7.3)
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte) VALUES
  ('extreme', 0, 3, 60, 1.5, 5000, 2, 0.65);    -- step_order=0 sorts first; fires at risk ≥ 0.65

-- SEVERE: same channels, longer waits, human relay still available
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte) VALUES
  ('severe', 1, 1, 180, 1.5, 8000, 2, NULL),
  ('severe', 2, 3, 120, 1.5, 8000, 2, NULL),
  ('severe', 3, 2, 300, 1.0, 0,    1, NULL),
  ('severe', 4, 7, 300, 1.0, 0,    1, NULL);    -- [v3.0] one relay attempt for severe

-- MODERATE: push + email only, no SMS spend, no relay (a human's time is the most expensive channel)
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte) VALUES
  ('moderate', 1, 1, 300, 1.5, 10000, 2, NULL),
  ('moderate', 2, 2, 600, 1.0, 0,     1, NULL);

-- MINOR: single push, no escalation
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte) VALUES
  ('minor', 1, 1, 0, 1.0, 0, 1, NULL);
```

**`human_relay` has `cost_weight = 12`, the highest in the table, and it is absent from `moderate` and `minor` entirely.** That is a deliberate, defensible policy statement encoded as data: **a human being's time and attention is the most expensive channel the platform has**, and spending it on a minor advisory would train relay operators to ignore the calls that matter. It also means the escalation engine — which already prefers cheap channels first — naturally treats a person as the last resort without a single line of special-case code.

## 21.2 Thunderstorm classifier and dedup (v2.1, unchanged)

```sql
-- Thresholds are meteorologically standard, not invented: CAPE > 1000 J/kg is the widely-used
-- "moderate instability" floor; Lifted Index < -2 is the standard "thunderstorms likely" ceiling.
-- Cite these two to a judge as domain-standard, not tuned-to-pass-a-demo.
INSERT INTO app_config (key, value, unit, note) VALUES
  ('thunderstorm.cape_floor',   '1000','J/kg', 'Standard moderate-instability threshold'),
  ('thunderstorm.cape_scale',   '500', 'J/kg', 'Sigmoid steepness — tune only after real labels'),
  ('thunderstorm.li_ceiling',   '-2',  'K',    'Standard "thunderstorms likely" Lifted Index'),
  ('thunderstorm.li_scale',     '2',   'K',    'Sigmoid steepness'),
  ('thunderstorm.alert_floor',  '0.55','score','Risk above which a synthetic CAP alert is emitted — start conservative'),
  ('dedup.similarity_threshold','0.72','cosine','Agglomerative cut — re-tune after the 200-pair label pass, record the tuned value AND the precision/recall it produced'),
  ('dedup.window_hours',        '6',   'hours', 'Bounds the O(n²) pairwise comparison in cluster()');
```

## 21.3 System-wide (v2.1, unchanged)

```sql
INSERT INTO app_config (key, value, unit, note) VALUES
  ('delivery.batch_size',            '100',  'recipients','§6.2 — one XADD per this many'),
  ('delivery.stream_maxlen',         '10000','entries',   'Redis Streams cap, approximate trim'),
  ('redis.daily_command_budget',     '16600','commands',  'Alert at 80% = 13280, Part 28. Re-derived in §1.4 for v3.0'),
  ('pwa.network_timeout_seconds',    '4',    'seconds',   'NetworkFirst cutover to cache'),
  ('pwa.alert_cache_max_age_seconds','86400','seconds',   '24h — older than this is stale even offline'),
  ('pwa.ack_retention_minutes',      '1440', 'minutes',   'BackgroundSync gives up after this'),
  ('api.rate_limit_per_ip',          '60',   'req/min',   'slowapi default'),
  ('api.rate_limit_dispatch',        '5',    'req/min',   'Tighter on /dispatch — a double-click storm must not double-send'),
  ('jwt.access_ttl_minutes',         '15',   'minutes',   ''),
  ('jwt.refresh_ttl_days',           '7',    'days',      '');
```

## 21.4 **[v3.0] Every new threshold this release introduces — 36 rows, each with its reasoning**

Rule 1 says thresholds live in config. Rule 10 says a decision must store its inputs. This block is what makes both true for the new features. **Every `note` is written to be readable aloud in Q&A** — "why 0.35 and not 0.5" has an answer in the database.

```sql
-- ═══ F3 DUAL AUTHORIZATION (Rule 12) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('approval.required.minor',    '1','approvals','One authorized officer is sufficient for an advisory'),
  ('approval.required.moderate', '1','approvals','One authorized officer is sufficient'),
  ('approval.required.severe',   '2','approvals','Independent second officer. UNIQUE(alert_id,approver_id) makes "independent" structural, not procedural'),
  ('approval.required.extreme',  '2','approvals','Independent second officer'),
  ('approval.authoritative_sources_auto_approve','true','bool',
     'Rule 12: an alert from a source flagged is_authoritative dispatches with provenance=authoritative_source and no human wait. A seismograph network IS the second pair of eyes. Our OWN thunderstorm model is is_authoritative=false and does NOT get this.'),
  ('approval.wait_alert_seconds','300','seconds',
     'If a severe/extreme alert sits unapproved this long, page the ops channel (Part 28). A governance gate that silently delays a life-safety alert is a hazard; we measure it.');

-- ═══ F1 QUALITY GATE ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('quality_gate.min_target_count','1','recipients',
     'An alert targeting zero recipients is always blocked — it is a targeting error, never an intent'),
  ('quality_gate.max_target_area_km2','50000','km2',
     'Above this, WARN not BLOCK. 50,000 km2 is larger than Kerala; a polygon that big is probably a drawing error, but a genuine cyclone warning can legitimately be huge — so a human decides, we only flag'),
  ('quality_gate.require_expiry','true','bool',
     'An alert with no expiry never leaves the active set and poisons every future dedup and fatigue calculation'),
  ('quality_gate.required_lang_for_severe','ml','lang',
     'Kerala case-study state: a severe alert must have a Malayalam version before dispatch'),
  ('quality_gate.required_lang_for_extreme','ml','lang','Same, for extreme');

-- ═══ F2 VERSIONING ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('versioning.cancel_inflight_on_supersede','true','bool',
     'A citizen who reconnects after v3 (evacuate) is live must not receive v1 (monitor) from a retry queue. pending/queued → expired; already-sent is left alone because you cannot unsend a message'),
  ('versioning.supersede_lock_ms','3000','ms',
     'Redis SET NX PX window serialising two officers escalating the same incident. The partial unique index is the guarantee; this lock only turns a 500 into a clean 409');

-- ═══ F4 ALERT FATIGUE ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('fatigue.window_minutes','30','minutes','Lookback for related alerts on the same incident'),
  ('fatigue.alert_count_floor','3','alerts','Third alert in the window triggers relabeling'),
  ('fatigue.relabel_prefix','URGENT UPDATE — ','string',
     'Prepended at message-build time. In config so it can be translated and tuned without a deploy'),
  ('fatigue.never_suppress','true','bool',
     'Hard invariant, asserted by a test. Fatigue changes WORDING and never prevents delivery. A suppressed extreme alert would be the worst bug this platform could have');

-- ═══ D8f COMMUNICATION VULNERABILITY ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('vuln.tower_count_floor','2','towers',
     'Fewer than 2 towers within 5km = single point of failure for the whole unit. From the OpenCelliD sample distribution across our two case-study districts; re-derive when national data lands'),
  ('vuln.terrain_ruggedness_ceiling','0.6','normalized',
     'Above this, terrain itself obstructs signal regardless of tower count — the Wayanad geometry'),
  ('vuln.historical_reach_floor_pct','50','percent',
     'A unit whose historical recipient reach is below this is structurally vulnerable even with towers present — this is the ground the other two factors cannot see');

-- ═══ D11f ASSISTANCE PRIORITY (Rule 10 — every weight explainable aloud) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('assistance.weight_version','v1-2026-08-14','string','Stamped into every case so a score is reproducible'),
  ('assistance.weight.response_severity','0.35','ratio',
     'Largest single weight: what the person told us they need dominates. Trapped outranks everything'),
  ('assistance.weight.hazard_severity','0.25','ratio','The same request during an extreme event outranks it during a moderate one'),
  ('assistance.weight.vulnerability','0.15','ratio','Reuses the EXISTING reach-risk score — no new model'),
  ('assistance.weight.proximity','0.15','ratio','Distance to the hazard polygon, normalised'),
  ('assistance.weight.time_waiting','0.10','ratio',
     'Smallest weight, deliberately: waiting must lift a case, but must never let waiting outrank someone newly trapped'),
  ('assistance.max_wait_minutes','120','minutes','Normalisation ceiling for time_waiting'),
  ('assistance.response_severity.trapped','1.0','score','Immediate threat to life'),
  ('assistance.response_severity.medical','0.9','score','Immediate threat to life, may be stationary'),
  ('assistance.response_severity.unable_to_evacuate','0.7','score','Threatened but not yet in immediate danger'),
  ('assistance.response_severity.other','0.4','score','Unknown need — triaged by a human'),
  ('severity.rank.extreme','1.0','score','Shared severity ranking, used by priority and elsewhere'),
  ('severity.rank.severe','0.75','score',''),
  ('severity.rank.moderate','0.5','score',''),
  ('severity.rank.minor','0.2','score','');

-- ═══ B9 HUMAN RELAY ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('relay.escalate_on_channels_exhausted','true','bool',
     '§7.4 — the branch that makes channels_exhausted not the end of the line'),
  ('relay.node_kind_priority','panchayat,police,health_worker,school,volunteer,shelter','csv',
     'Order in which relay nodes are tried. Institutional before individual: a panchayat office has a duty of care a volunteer does not'),
  ('relay.confirm_timeout_minutes','20','minutes','No DTMF confirmation in this window → re-call once, then record relay.unconfirmed');

-- ═══ B8 ASSURANCE + B10 PEER RELAY ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('assurance.receipt_nonce_ttl_minutes','240','minutes',
     'A service-worker receipt nonce is valid this long — covers a phone that was off for hours, without leaving a forgeable window open indefinitely'),
  ('pwa.receipt_retention_minutes','1440','minutes','BackgroundSync retention for receipts'),
  ('relay.peer_enabled','true','bool','Kill switch — if Web Bluetooth misbehaves on the demo device, one UPDATE hides the feature entirely with no redeploy'),
  ('relay.peer_max_hops','1','hops',
     'ONE. This is peer relay, not mesh. Recorded as config so the number in the UI, the docs and the pitch cannot drift from the code');

-- ═══ ASSURANCE TIER FLOORS (Part 38 violation B) ═══
-- What counts as "reached" is a POLICY decision, not an implementation detail.
INSERT INTO app_config (key, value, unit, note) VALUES
  ('reachability.reached_tier_floor','2','tier',
     'Tier 2 = device_delivered. Provider-acceptance (tier 1) is explicitly NOT "reached" — a provider taking a message is not a device receiving it. This one row is the difference between an honest reach figure and a flattering one'),
  ('reachability.acknowledged_tier_floor','4','tier',
     'Tier 4 = acknowledged. A human acted');

-- ═══ IVR GATHER (Part 38 violation E) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('ivr.gather_digits','1','digits','Single keypress — the whole point of the IVR path is that it works for a stressed, possibly low-literacy user'),
  ('ivr.gather_timeout_s','10','seconds',
     'How long to wait for a keypress. Ten seconds is generous on purpose: this person may be evacuating. Tune on the real demo calls, not by guessing');

-- ═══ B10 CHUNKING (Part 38 violation D) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('relay.peer_chunk_bytes','480','bytes',
     'Below the common BLE default MTU payload after ATT overhead. Different Android stacks negotiate different MTUs, so this WILL be tuned on the two real demo devices — which is exactly why it is a row and not a literal');

-- ═══ BASEMAP (§1.6.5) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('map.tile_source','pmtiles_local','enum',
     'pmtiles_local | openfreemap. MUST be pmtiles_local for the demo — a hosted basemap goes BLANK when the network is unplugged at 4:45 in the script. Day-11 snapshot verification asserts this value');

-- ═══ E4 ENROLLMENT ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('enrollment.sms_keyword_register','REGISTER','string','Inbound keyword; case-insensitive'),
  ('enrollment.sms_keyword_stop','STOP','string','Opt-out. Honoured immediately and permanently, TRAI-aligned'),
  ('enrollment.csv_max_rows','5000','rows','Per-import cap — bounds a single request and a single audit event'),
  ('enrollment.csv_require_dry_run','true','bool',
     'A destructive bulk write must be previewed first. Enforced server-side, not just in the UI');
```

**`relay.peer_max_hops = 1` deserves a note about why it is config at all**, given it will never change during this build: it exists so that **the number in the code, the number in the UI disclosure, and the number in the pitch are physically the same number.** A "one hop" claim in a slide and a `for` loop that could do two is exactly the kind of drift that gets caught on stage.

---

# PART 22 — THE ML SERVICE WILL OOM ON A FREE RENDER INSTANCE. HERE IS THE FIX.

**The gap:** Render's free web service is **[RECONFIRM]** ~512 MB RAM / 0.1 shared vCPU. `paraphrase-multilingual-MiniLM-L12-v2` is ~470 MB fp32. `indictrans2-en-indic-dist-200M` is ~1.2 GB fp32, several hundred MB int8. **PyTorch's import footprint alone is 300–500 MB.** All of it plus FastAPI in 512 MB does not degrade gracefully — it OOM-kills on the first real inference, and because Render's health check just sees the process restart, this masquerades as "flaky cold starts" for days.

**The fix — split the topology, keep it at ₹0:**

1. **`services/api` stays on Render** and never imports `torch`, `transformers`, or `sentence-transformers`. It runs FastAPI, the delivery engine, the state machine, PostGIS queries, and the LightGBM reach-risk model (a boosted-tree model — a few MB, genuinely fine in 512 MB).
2. **`services/ml` becomes its own Hugging Face Space**, `cpu-basic` — **[RECONFIRM]** historically far more RAM than Render's free tier, which is the entire point. Packaged as a small FastAPI app (HF Spaces supports a plain Docker/FastAPI SDK) exposing exactly two endpoints:
   ```
   POST /embed      {"texts": [...]}                    → embeddings for dedup clustering
   POST /translate  {"text": ..., "target_lang": ...}   → translated string
   ```
3. **Auth between the two:** a single shared-secret header (`X-Internal-Key`), value in both services' env, never in git.
4. **Both models load once at Space startup**, not per-request. HF Spaces free also sleeps on inactivity — mitigate exactly like Render's cold start: add a second `curl` line to `keepalive.yml` (already done, Part 15).
5. **The demo path is unaffected.** Translations for the alerts shown live are pre-generated and cached in Postgres days before the pitch. The Space can be asleep during the demo and nothing breaks, because the demo never calls `/translate` live — only reads the cache. Dedup clustering is a background job, off the 6-minute critical path.
6. **If HF free hardware is smaller than remembered** (Day-1 check), quantize both models to int8 via `optimum`/`bitsandbytes` and accept a small accuracy hit — never silently ship the OOM-prone all-in-one topology.

**[v3.0] One addition:** `services/crypto/alert_signing.py` uses **PyNaCl**, which is ~2 MB and has no Torch dependency, so **alert signing stays on the Render API service.** It must — signing has to happen synchronously at publish time, and routing it through a sleeping HF Space would put a 50-second cold start in the dispatch path. Verified against the Part 33 checklist: `services/api` still has zero `torch`/`transformers` imports.

**Definition of done:** a Day-2 smoke test calling `/embed` and `/translate` on the Space 20× back-to-back without a restart, while the Render app independently serves 50 req/s of `/api/v1/units` — proving the failure domains are isolated.

---

# PART 23 — CONNECTION POOLING

Neon offers a **direct** connection and a **pooled** one (PgBouncer transaction mode, `-pooler` hostname suffix — **[RECONFIRM]** exact format at `neon.com/docs/connect/connection-pooling`). Free-tier direct-connection ceilings are low enough that a WebSocket console (Part 13 targets 50 concurrent clients) plus the ingestion poller plus delivery workers, all direct, is a realistic way to hit a wall during your *own* rehearsal.

```python
# services/api/db.py
POOLED_URL = settings.database_url_pooled      # ends in "-pooler.<region>.neon.tech"
DIRECT_URL = settings.database_url_direct      # migrations only

# Pool sizing comes from ENV, not from app_config — and this is the one documented
# exception to Rule 1's "config table" default: you cannot read a config table before
# you have a connection pool to read it with. Part 38 records this bootstrap exception.
engine = create_async_engine(
    POOLED_URL,
    pool_size=settings.db_pool_size,            # DB_POOL_SIZE
    max_overflow=settings.db_pool_max_overflow, # DB_POOL_MAX_OVERFLOW
    pool_timeout=settings.db_pool_timeout_s,    # DB_POOL_TIMEOUT_S
)
```
```bash
alembic -x db_url=$DATABASE_URL_DIRECT upgrade head
```

**[v3.0] Two new pressures on the pool, both accounted for:**
- **A second WebSocket endpoint** (`/ws/incidents/{id}`) for the Command Board and assistance queue. **It shares the same throttled Redis pub/sub channel** as `/ws/alerts/{id}` rather than opening its own query loop — so it adds subscribers, not connections.
- **Provider webhooks are now high-frequency.** Twilio status callbacks arrive per-message, and each one does a `by_provider_ref` lookup. That is why `delivery_provider_ref_ix` exists (§5.6) — without the index, a burst of 340 status callbacks becomes 340 sequential scans on the delivery table and the pool starves during exactly the moment the demo is running.

**The load test (Part 13) runs against the pooled URL specifically**, and **[v3.0]** now includes a webhook burst: 340 simulated Twilio callbacks in 10 seconds, concurrent with 50 WS clients.

---

# PART 24 — RETRY BACKOFF: EXPONENTIAL WITH JITTER, NOT A FLAT NUMBER

A flat `wait_before_next_s` treats a channel down for one second the same as one down for ten minutes — every queued recipient gets hammered at a fixed cadence, which turns "FCM is briefly slow" into "we exhausted our retry budget against a channel that was about to recover."

```python
# services/delivery/retry.py
import random

def backoff_delay(attempt: int, step) -> float:
    """attempt is 1-indexed. step carries wait_before_next_s, backoff_multiplier,
       jitter_ms — all from escalation_policy, per Rule 1. No literals here."""
    base = step.wait_before_next_s * (step.backoff_multiplier ** (attempt - 1))
    capped = min(base, step.max_wait_s if step.max_wait_s else base)
    jitter = random.uniform(0, step.jitter_ms / 1000)
    return capped + jitter
```

The jitter term specifically stops 340 queued retries for the same failed batch from firing in the same Redis-command-spending instant — which matters doubly because of the 16,600/day budget: a synchronized retry storm is a *quota* incident as well as a *load* incident.

---

# PART 25 — THE COMPLETE SECRETS & ENV VAR CHECKLIST

One list, owned by D6, checked off once per environment (local / CI / demo). Anything not on this list should not exist in any service's config. **CI fails the build if any key here is missing from `.env.example`** (`scripts/check_env_example.py`).

| Var | Used by | Rotation trigger |
|---|---|---|
| `DATABASE_URL_POOLED` | api, delivery worker | On suspected leak |
| `DATABASE_URL_DIRECT` | migrations only | Same |
| `REDIS_URL` | api, delivery worker | Same |
| `FCM_SERVICE_ACCOUNT_JSON` | delivery/channels/fcm | If committed by accident |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | sms, ivr, **[v3.0] human_relay, sms-inbound** | Immediately if it touches a public log |
| `TWILIO_WEBHOOK_AUTH_TOKEN` | **[v3.0]** webhook signature verification | With the auth token |
| `BREVO_API_KEY` | delivery/channels/email | — |
| `OPENCELLID_TOKEN` | ml/reach_failure feature build | — |
| `HF_SPACE_URL` / `INTERNAL_ML_KEY` | api ↔ ml (Part 22) | Rotate `INTERNAL_ML_KEY` once, deliberately, pre-freeze — proves the path works before you need it under pressure |
| `JWT_SIGNING_SECRET` | api auth | Rotate once pre-freeze, same reason |
| `SENTRY_DSN` | all services | — |
| `WEBHOOK_HMAC_SECRET` | api/webhooks | Per-provider where supported |
| **`PHONE_HASH_PEPPER`** | **[v3.0]** enrollment, dedupe, STOP lookup | **Never rotate during the build.** Rotating it invalidates every `phone_hash` and silently breaks dedupe. If it must rotate, it is a migration with a full recompute, not an env change |
| **`ALERT_SIGNING_SEED_B64`** | **[v3.0]** `services/crypto` (Ed25519 private seed) | If leaked, **rotate immediately and ship a new PWA bundle** — the public key is baked into the client, so a rotation is a client release. Recorded so nobody treats it as a routine env swap |
| **`ALERT_SIGNING_PUBKEY_B64`** | **[v3.0]** PWA build-time constant | Public by design; ships in the bundle; safe to commit to the build config |
| `SLACK_OR_DISCORD_ALERT_WEBHOOK` | Part 28 monitoring | If leaked, low severity — regenerate |
| `GITHUB_TOKEN` (Actions default) | keepalive.yml, snapshot.yml | Auto-rotated by GitHub |

**The two v3.0 secrets have unusual rotation semantics and that is why they get sentences instead of a dash.** `PHONE_HASH_PEPPER` is a *data-shaping* secret — rotating it is a migration. `ALERT_SIGNING_SEED_B64` is a *client-coupled* secret — rotating it is a release. Neither behaves like an API key, and discovering that during an incident would be a bad afternoon.

---

# PART 26 — RBAC PERMISSION MATRIX

This table **is** the spec for the FastAPI dependency, not prose about it. One test per row, allow and deny (Part 13, Day 10).

| Endpoint | citizen | officer | state_admin | auditor | **[v3.0] relay_node** |
|---|---|---|---|---|---|
| `POST /alerts` (compose) | ❌ | ✅ | ✅ | ❌ | ❌ |
| `GET /alerts`, `/alerts/{id}` | ✅ (own-area) | ✅ | ✅ | ✅ | ❌ |
| `POST /alerts/{id}/preview` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `POST /alerts/{id}/validate` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `POST /alerts/{id}/approve` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `POST /alerts/{id}/dispatch` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `POST /alerts/{id}/new-version` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `GET /alerts/{id}/deliveries` | ❌ | ✅ (own district) | ✅ | ✅ | ❌ |
| `GET /alerts/{id}/assurance` | ❌ | ✅ (own district) | ✅ | ✅ | ❌ |
| `GET /alerts/{id}/audit` | ❌ | ✅ (own district) | ✅ | ✅ (full, unfiltered — P4's whole reason to exist) | ❌ |
| `GET /alerts/{id}/report.pdf` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `GET /incidents`, `/incidents/{id}` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `GET /incidents/{id}/timeline` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `GET /incidents/{id}/board` | ❌ | ✅ (own district) | ✅ | ✅ | ❌ |
| `POST /incidents/{id}/close` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `GET /incidents/{id}/after-action` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `POST /ack`, `POST /response` | ✅ | ✅ | ✅ | ❌ | ✅ |
| `POST /deliveries/{id}/receipt` | ✅ (nonce-gated, not role-gated) | ✅ | ✅ | ❌ | ✅ |
| `GET /assistance`, `/assistance/{id}` | ❌ | ✅ (own district) | ✅ | ⚠️ **aggregate only — never point geometry** (§12.2) | ❌ **never** |
| `PATCH /assistance/{id}` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `GET /relay/tasks` | ❌ | ✅ | ✅ | ✅ | ✅ **own unit only** |
| `POST /relay/tasks/{id}/confirm` | ❌ | ✅ | ✅ | ❌ | ✅ own unit only |
| `POST /admin/recipients/import` | ❌ | ✅ (own district) | ✅ | ❌ | ❌ |
| `GET /units`, `/units/{id}/risk` | ✅ (public aggregate) | ✅ (full) | ✅ | ✅ | ❌ |
| `GET /units/{id}/reachability` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `GET /units/{id}/vulnerability` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `GET /analytics/*` | ❌ | ✅ (own district) | ✅ | ✅ | ❌ |
| `GET /models` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `GET /methodology` | ✅ (it's the transparency page) | ✅ | ✅ | ✅ | ✅ |
| `POST /webhooks/*` | n/a — HMAC-authenticated, never user-authenticated | | | | |
| **Individual contact reveal** | ❌ | ✅, itself an audit event | ✅, itself an audit event | ❌ — sees *that* a reveal happened, never the PII | ❌ |

**Three rows carry the whole privacy design:**

1. **`auditor` on `/assistance`** — aggregate only. An auditor proving the state responded does not need a map of which houses had someone trapped inside.
2. **`relay_node` on `/assistance`** — **never**, at any scope. The relay operator gets a count and an area (§12.2). This is the row most implementations would get wrong, and getting it right costs nothing but a decision.
3. **`auditor` on contact reveal** — an auditor who could read raw phone numbers would defeat the entire point of `phone_enc` existing. Auditor access is to *proof the system behaved correctly*, not to the PII the system protects.

---

# PART 27 — FEATURE FREEZE, ENFORCED BY THE REPO

Risk #9 is rated **High probability / Severe impact** — the worst combination on the register. A rule with no mechanism erodes at 1 a.m. on the 22nd when someone's "quick fix" is actually a feature.

```yaml
# .github/workflows/freeze-guard.yml
name: freeze-guard
on: [push, pull_request]
jobs:
  check-freeze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Block non-hotfix changes after freeze
        run: |
          FREEZE_EPOCH=$(date -d "2026-08-21T21:00:00+05:30" +%s)
          NOW_EPOCH=$(date +%s)
          if [ "$NOW_EPOCH" -gt "$FREEZE_EPOCH" ]; then
            if ! echo "${{ github.event.head_commit.message }}" | grep -qi "\[hotfix-approved\]"; then
              echo "::error::Feature freeze is in effect (21 Aug 21:00 IST). Commits after freeze require [hotfix-approved] in the message, added only after two teammates agree in the team channel."
              exit 1
            fi
          fi
```

Paired with a branch-protection rule on `main` requiring at least one review, so the freeze-guard job is actually checked before merge rather than informationally red after the fact.

**[v3.0] The protected surface grows with the codebase** — a freeze guard that only watches v2.1's directories is not a freeze guard:

```yaml
      - name: Guarded paths must not change post-freeze
        run: |
          GUARDED="services/delivery services/targeting services/governance \
                   services/response services/enrollment services/crypto \
                   web/citizen/src/relay.ts web/citizen/src/verify.ts \
                   web/console/src/pages/CommandBoard.tsx \
                   web/console/src/components/AssuranceLadder.tsx \
                   data/seeds migrations"
```

**Rollback safety net:** tag the working state every night, not just at freeze.
```bash
git tag -a "nightly-$(date +%Y%m%d)" -m "End of day snapshot, all tests green" && git push --tags
```
If Day 12's rehearsal finds a regression nobody can quickly diagnose, `git checkout nightly-20260820` is a known-good state to demo from while the bug gets found calmly, after the pitch.

---

# PART 28 — MONITORING THRESHOLDS THAT ACTUALLY TRIGGER SOMETHING

Part 14 names the dashboards. Here is what makes someone look at them before it's too late, given that nobody on a six-person team watches Grafana for ten straight days.

| Signal | Threshold | Action | Mechanism (₹0) |
|---|---|---|---|
| `redis_commands_today` | > 80% of 16,600 (13,280) | Ping the team channel | A scheduled GitHub Action (every 30 min) reading the counter via the metrics endpoint, `curl`ing a Slack/Discord incoming webhook |
| API `p95` latency | > 800 ms sustained 5 min | Same webhook | Same Action, second check |
| Render `/health` | 3 consecutive failures | Webhook + auto re-trigger via `keepalive.yml` | Extend the existing cron |
| HF Space `/health` | 3 consecutive failures | Same | Same pattern, second URL |
| Sentry event volume | Approaching **[RECONFIRM]** free-plan quota | Set `SENTRY_ENABLED=false` during Locust runs specifically | Load testing is the single most likely way to burn a month's error quota in one afternoon, and it buys nothing — load-test errors are expected, not diagnostic |
| Twilio trial **credit** (SMS count **and voice minutes**, Trap 13) | Approaching exhaustion | Stop non-essential real sends; rehearse on the simulated adapter | **[v3.0] Now mandatory, not advisory** — five consumers share the cap (Risk #8). A one-line counter check before every manual send from Day 18; reserve the remainder for rehearsal + the one real demo message |
| **[v3.0]** `alerts_blocked_by_quality_gate{rule_id}` | Any single rule > 50% of blocks | Review that rule | Either the rule is wrong or the composer is missing a field. Both fixable, neither visible without this |
| **[v3.0]** `approval_wait_seconds` p95 | > `approval.wait_alert_seconds` (300) | Page the ops channel | A governance gate that silently delays a life-safety alert is a hazard. We measure our own safety feature's cost |
| **[v3.0]** `assistance_queue_depth{status='new'}` | Growing 10 min with zero assignments | Page | The queue's real failure mode isn't a bug, it's nobody looking at it |
| **[v3.0]** `peer_relay_signature_failures_total` | **> 0** | Investigate | Should be exactly zero. Anything else is a bug or an attempt (Rule 11) |
| **[v3.0]** `relay_unavailable_total{unit}` | Any | **No page — a report line** | Deliberately not an alert. "This village has no relay coverage" is a *preparedness finding* for the after-action report, not a 3 a.m. incident |

**Demo-day runbook** (Part 17's six minutes only work if the 30 minutes before them are planned):

- **T-30 min:** D6 opens the console and leaves it open (Render pre-warm). D1 confirms USGS/GDACS ingestion ran in the last hour with no quarantine spike. D2 confirms the Twilio trial has ≥3 verified numbers and **≥5 sends remaining**. **[v3.0]** D6 confirms `test_snapshot_completeness` passed against the committed snapshot, and **Officer B's laptop is awake, logged in, on the approval screen.**
- **T-10 min:** the presenter does one silent dry run on their own machine, camera off, confirming nothing changed since last night's tag. **[v3.0]** D5 confirms the two Bluetooth demo devices are paired, charged, and one is already in airplane mode.
- **During:** one teammate (not the presenter) watches the webhook channel silently, phone on vibrate, intervening only if asked.
- **If anything red fires mid-pitch:** the backup video is already open in a second tab — the presenter's job is to know the one sentence that transitions to it without breaking stride, rehearsed as its own beat in Phase 5, not improvised.

---

# PART 29 — THE DEM RISK IS SMALLER THAN THE REGISTER MAKES IT SOUND

Risk #7 says "no India tile in GLO-30's released set" — scoped to the whole country, which is both harder to check and scarier than reality. The actual dependency is `terrain_ruggedness` for **exactly two case-study districts**: Wayanad (≈11.6°N, 76.1°E) and Palghar (≈19.7°N, 72.8°E).

Copernicus tiles are named by their 1°×1° lower-left corner. The real Day-1 check is four lookups:

```bash
for tile in N11_00_E076_00 N19_00_E072_00 N19_00_E073_00 N11_00_E077_00; do
  aws s3 ls --no-sign-request \
    "s3://copernicus-dem-30m/Copernicus_DSM_COG_30_${tile}_DEM/" \
    && echo "OK: $tile" || echo "MISSING: $tile — fall back to SRTM for this cell only"
done
```

The two districts' centroids each sit near adjoining 1° cells, so four candidate tiles makes the check conservative. If any is missing, SRTM applies **only to that cell** — mixing DEM sources per-cell is fine, since ruggedness is computed per admin-unit and each unit's centroid falls in exactly one cell. A four-line shell check with a per-cell fallback, done in the first hour, with a committed dated log.

---

# PART 30 — OPENCELLID: WHAT HAPPENS IF APPROVAL SLIPS

**Fallback, in order:**
1. Register on Day 1 regardless of build sequencing — free and asynchronous.
2. If not approved by Gate 2, build `unit_features` with `terrain_ruggedness`, `population`, `building_count`, `alert_severity`, `hour_of_day`, `rainfall_intensity` only — **a 5-feature bootstrap model, not a 6-feature one.** Extend the `disclosure` string: *"Connectivity features (tower density) pending community-API approval; the published failure process runs on terrain, population, building density and weather alone until they land."*
3. The moment the token clears — Day 5, Day 10, whenever — tower features are added as a strict feature-set upgrade with a `model_registry` version bump. No redesign, just a later `INSERT`.

**[v3.0] One new consequence, handled in the SQL rather than in a comment.** D8f's vulnerability view reads `tower_count_5km`. If OpenCelliD slipped, that column is NULL — and a naive view would silently classify every unit as `standard` (not vulnerable), which is the **worst possible failure mode**: a preparedness map that says everything is fine because a feature is missing. §5.12's view therefore returns `'unknown_connectivity_features_pending'` when the column is NULL, and the UI renders that literally. **A missing input produces "unknown," never "fine."** Same principle as Rule 8, applied one layer down.

---

# PART 31 — NDMA DOCUMENT SOURCING: RETRY BEFORE DECLARING UNREACHABLE

**Concrete task (D4, ~30 minutes, not open-ended):**
1. Retry `ndma.gov.in`'s guideline pages **three times, ten seconds apart, from two different networks** (a teammate's hotspot and the college Wi-Fi) before concluding it's a real block rather than a transient failure or one flaky path.
2. If still unreachable, the fallback corpus is specifically: the **Disaster Management Act 2005** full text on `indiacode.nic.in` (India's official statute repository, structurally far more stable than a ministry CMS); **Kerala SDMA's and Maharashtra SDMA's** published District Disaster Management Plans (the two states this build already centres on — a natural, non-arbitrary corpus); and any NDMA guideline PDFs already re-hosted by a state SDMA even if `ndma.gov.in` itself is down.
3. Whatever is retrieved gets the same `source_id`/`fetched_at`/`checksum` provenance treatment as every other number (Rule 4). A RAG corpus with no provenance trail would be a strange thing to ship in a platform whose pitch is "every number is traceable."

Still [S] stretch and independently cuttable — this section only makes the fallback concrete enough that D4 doesn't spend a day deciding what "published State DM Plans" means at 11 p.m.

---

# PART 32 — `check_no_hardcoding.py`: WHAT IT ACTUALLY DOES

```python
#!/usr/bin/env python3
"""scripts/check_no_hardcoding.py — Rule 1, mechanically enforced.
Fails if a bare numeric literal appears in a comparison or arithmetic
expression inside the guarded directories, outside the allowlist.
"""
import ast, sys, pathlib
from typing import NamedTuple

GUARDED_DIRS = ["services/delivery", "services/targeting",
                "services/governance", "services/response"]   # [v3.0] + two new packages
ALLOWED_LITERALS = {0, 1, -1, 2, 100}   # array indices, percentages, the batch-of-2 idiom
ALLOWED_CONTEXTS = (ast.Subscript,)      # a[0] is an index, not a threshold

class Violation(NamedTuple):
    file: str; line: int; value: object

def scan_file(path: pathlib.Path) -> list[Violation]:
    tree = ast.parse(path.read_text(), filename=str(path))
    for parent in ast.walk(tree):                     # one-line parent-linking pass
        for child in ast.iter_child_nodes(parent):
            child._check_parent = parent              # type: ignore[attr-defined]
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Compare, ast.BinOp)):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
                    if child.value in ALLOWED_LITERALS:
                        continue
                    if isinstance(getattr(child, "_check_parent", None), ALLOWED_CONTEXTS):
                        continue
                    violations.append(Violation(str(path), child.lineno, child.value))
    return violations

def main() -> int:
    all_violations = []
    for d in GUARDED_DIRS:
        for f in pathlib.Path(d).rglob("*.py"):
            all_violations += scan_file(f)
    for v in all_violations:
        print(f"::error file={v.file},line={v.line}::Bare literal {v.value!r} in a decision "
              f"position inside a Rule-1-guarded directory. Move it to app_config "
              f"or escalation_policy.")
    if not all_violations:
        print(f"check_no_hardcoding: clean across {GUARDED_DIRS}")
    return 1 if all_violations else 0

if __name__ == "__main__":
    sys.exit(main())
```

The allowlist is short and reviewed in PR — the point isn't a zero-false-positive linter, it's that **every exception is a visible, reviewed line in this file**, not a silent literal buried in `delivery/engine.py`. **[v3.0]** The two new guarded packages are where the most literal-prone new code lives: the priority formula and the fatigue window. A hardcoded `0.35` in a priority weight is exactly the thing that survives review and then cannot be explained in Q&A.

**[v3.0] The Part 33 rule stands and is worth repeating:** if this script never fires once during the whole build, treat that as **suspicious, not as success.**

---

# PART 33 — DEFINITION OF DONE, DELTA

Superseded by **Part 19**, which merges v2.0's Part 19, v2.1's Part 33, and v3.0's additions into one list. Nothing from either earlier list was dropped; Part 19 is the single checklist to walk on Day 11.

---

# PART 34 — **[v3.0] TRACEABILITY: WHERE EVERY REVIEW FINDING LANDED**

Three independent review passes produced this release. Every finding is traced to a feature and a part, so nothing was quietly absorbed or lost.

| Source of the finding | Finding | Landed as | Part |
|---|---|---|---|
| Pass 1 (reachability/relay) | "Alert sent successfully" is not a useful statement — publish a per-area Reachability Score | **D7f**, with a second denominator we added (population *and* recipients) | §5.12, 11.2 |
| Pass 1 | One connected phone should be able to relay to nearby offline devices | **B10**, re-specified per Trap 12 as one-tap peer relay with Ed25519 verification | §8.7, Rule 11 |
| Pass 2 (governance/lifecycle) | An alert is treated as a delivery object, not a lifecycle | **F2** | §5.4, 7.3 |
| Pass 2 | High-severity alert creation needs governance | **F3**, extended with Rule 12's machine-provenance path | §5.5, Rule 12 |
| Pass 2 | "Delivered" is too broad as an assurance statement | **B8**, extended with the `channel_capability` table and Rule 8 | §5.7, 8.2 |
| Pass 2 | "I'm Safe" is not enough | **C6**, plus the DTMF mapping so it works on a feature phone | §11.5, 8.4 |
| Pass 2 | Assistance requests have nowhere operational to go | **D11f**, with Rule 10 factor storage | §5.8, 9.6 |
| Pass 2 | No pre-dispatch quality gate | **F1** | §2.1 (code), Part 21 |
| Pass 2 | Escalation should learn from history | **Rejected** — needs data we won't have | Part 35 |
| Pass 2 | Identify structural communication dead zones | **D8f** | §5.12 |
| Pass 2 | Digital delivery will always have blind spots — trusted human relay | **B9**, plus the `relay.unavailable` finding and §12.2's privacy design | §8.6, 7.4 |
| Pass 2 | "Nearest shelter" isn't the best shelter | **Descoped** — no live occupancy source exists | Part 35 |
| Pass 2 | Evacuation routes need operational context | **Partially built** — hazard-polygon avoidance only (§4.6); live closures rejected | §4.6, Part 35 |
| Pass 2 | Need a real incident command view | **D9f** | §11.2 |
| Pass 2 | Need a chronological operational record | **D10f** | §5.10 |
| Pass 2 | Delivery % hides warning lead time | **D13f**, with the seismic-exclusion honesty | §4.5, 5.12 |
| Pass 2 | The system should explain automated decisions | **D12f** + Rule 10 | §9.2, 9.6 |
| Pass 2 | Too many warnings cause fatigue | **F4**, never-suppress invariant | Part 21 |
| Pass 2 | Evidence should continue after the incident | **D14f** [S] | §10 |
| Pass 3 (gap analysis) | No citizen enrollment pipeline at all | **E4** | §12.1, Part 21 |
| Pass 3 | Nothing detects a unit-wide blackout automatically | **D8f + §7.4's `relay.unavailable`** — a named audit event, not a red dot someone must notice | §7.4 |
| Pass 3 | A "delivered" receipt isn't a human being informed | **B8**, and the honesty of what it cannot claim | §8.2 |
| Pass 3 | Consent-gating vs. reach is unresolved | **Resolved as policy, in writing** — §12.3's three channel classes | §12.3 |
| Pass 3 | Officer console has no offline story | **Rejected** — budget-bound (₹0) | Part 35 |
| Pass 3 | Community radio / AIR / cable TV | **Rejected** — institutional access, unobtainable | Part 35 |
| Pass 3 | Real siren/PA hardware | **Rejected** — budget-bound | Part 35 |
| Pass 3 | No household-level modeling | **Open, disclosed** | Part 35 |
| Pass 3 | Overlapping/competing alerts have no contention policy | **Open, disclosed** | Part 35 |

---

# PART 35 — **[v3.0] THE REJECTED AND DEFERRED REGISTER**

Nothing here was forgotten. Each row was considered, and each has a reason that is either **physics, law, money, or data we will not have** — never "we ran out of time," because that reason would deserve a different decision.

## 35.1 Rejected — cannot be built honestly, at any effort

| Capability | Reason | Would need |
|---|---|---|
| **Community radio / All India Radio / cable TV broadcast** | **Institutional access, not engineering.** No self-service API exists; injection into a broadcast feed requires a signed agreement with a broadcaster or ministry | An MoU. Not obtainable by a student team on any timeline |
| **Live road-closure data for evacuation routing** | **No free public source exists for India.** Showing a closure without one is fabricating a road condition — a genuinely dangerous class of fake data in a life-safety tool | A state PWD or traffic-authority feed. §4.6 ships hazard-polygon avoidance instead, and says so on screen |
| **Automated live shelter occupancy** | **No live source exists, free or paid.** OSM gives locations, never capacity | A state shelter-management system integration. *Manual officer entry, timestamped and labelled "manually entered," would be legitimate and is a natural v3.1 item* |
| **Nationwide production SMS** | **Regulatory.** TRAI DLT registration requires a registered legal entity and ~10 business days | A legal entity. Already disclosed in the pitch (§8.5) since v2.0 |
| **Multi-hop Bluetooth mesh** | **Browsers cannot do background BLE scanning or unprompted relay** (Trap 12) | A native app. Peer relay (one hop, one tap) is the honest browser-native version |

## 35.2 Rejected — technically possible, but would violate a rule of this document

| Capability | Which rule it would break |
|---|---|
| **Channel Reliability Intelligence** (learned per-unit channel success rates) | **Rule 6 + Rule 13.** By demo day we will have run a few dozen dispatches. A "Push 94% / SMS 82%" table on that data is a made-up number wearing a model's clothes. The honest version needs months of real traffic — and the architecture that *collects* it is exactly what B8 ships. **This is a v3.1 feature whose data pipeline is being built now** |
| **Full impact-based targeting** (hazard-intensity surface) | **Rule 13 + Rule 4.** Needs a verified flood-depth/intensity raster we do not have. The lightweight composite — severity × exposure × existing reach-risk, all real fields — is available if time permits and is honestly a different, smaller claim |
| **Email open-pixel tracking** | **Rule 8's spirit.** Technically trivial, and we declined it: a privacy intrusion whose signal is unreliable (blocked pixel ≡ unopened email). Recorded in `channel_capability.not_applicable_reason` so the refusal is public |
| **Consent-override for individually-addressed channels in extreme events** | **v2.1's `test_no_delivery_without_consent`.** §12.3 resolves the tension the right way instead: area broadcast and human relay reach the unconsented without misusing anyone's data |
| **Handing relay operators a household list** | **§12.2.** Operationally more efficient; leaks who in a village asked for medical help, to a semi-trusted community member. Count-and-area only |

## 35.3 Deferred — budget-bound (₹0 charter), not capability-bound

| Capability | Note |
|---|---|
| **Real siren/PA hardware trigger** (ESP32 + GSM/LoRa) | Works, costs money, and needs on-stage reliability testing days before a freeze. The simulated webhook plus honest disclosure is the safer call. *If a teammate already owns the parts, revisit — but not after Day 8* |
| **GSM-modem fallback for the officer console** | Same. The DEOC-offline gap remains **open and disclosed** |

## 35.4 Open and disclosed — no feature proposed, stated in the pitch as a known limitation

| Gap | Why it stays open |
|---|---|
| **Officer console requires internet** | Budget (35.3). If the DEOC's own connectivity dies, dispatch is blocked — a real limitation of a cloud-hosted system |
| **Household vs. individual modeling** | One shared phone per household is common in rural India. We track push tokens and phone numbers, so "reached the household" and "reached the individual" are indistinguishable to us. **This is precisely why D7f shows a population-based denominator** — it makes the ambiguity visible rather than hiding it inside a recipient count |
| **Overlapping/competing alerts** | Two hazards for one area at once have no contention policy for the shared SMS and Redis budget, and no merge rule for the citizen's screen. Dedup handles *same-event* duplication (§9.1); *different-event* concurrency is unhandled |
| **Free-tier ceilings** | Neon 0.5 GB, Upstash 500K/month, Render 512 MB are hackathon constraints. A production deployment is a paid-tier migration, not a rewrite — but it is not free |
| **Reach-risk validated at n=2** | Wayanad and Palghar. Stated out loud, every time |
| **Voice/IVR localisation coverage** | IVR `<Say>` uses the C3 translation cache, so the *text* is localised; TTS voice quality across all 22 scheduled languages is **untested at v3.0** and should be verified for the two demo languages only. Anything beyond that is an unverified claim |

**This register is the part of the document a senior reviewer reads first.** A 42-feature list with no rejected column is a wishlist. A 42-feature list with a 20-row rejected register, each row carrying physics, law, money, or missing data as its reason, is a plan.

---

# PART 36 — **[v3.0] CLOSING NOTE**

v2.1 closed every loose end in v2.0. This pass did the same thing to v2.1, and then did something harder: it added seventeen features **at Day 4 of a 13-day build without touching a single dependency, without a new external data source, without a new ML model, and without modifying the one module that carries a 95% coverage floor.**

That was possible for exactly one reason, and it is the reason worth saying out loud if a judge asks how six people did this in ten days: **v2.0's Rule 1 and Rule 2 were enforced from Day 0 rather than retrofitted.** Because every threshold already lived in a config table, thirty-one new thresholds were thirty-one `INSERT`s. Because every channel already sat behind a Protocol, the human-relay channel was one new class and one seed row. Because the audit ledger was already append-only and hash-chained, the incident timeline was a `SELECT`. **The discipline was the feature; the seventeen features were the interest it paid.**

The honest summary of what changed:

- **Six things the platform can now do that it could not:** know whether an alert was *authorized*, know which *version* a citizen received, distinguish "a provider took it" from "a human was informed," receive an answer when that human is **not** safe, route that answer to a responder with an explainable priority, and **send a person** when every wire is down — recording it separately, because a person is not a receipt.
- **Two things it can now refuse to claim, in public, with reasons in the database:** SMS read receipts, and email opens. **The struck-through rung with its reason beside it is the single most defensible component in the product.**
- **One thing it can now name that nobody else measures:** the villages where the last resort does not exist. `relay.unavailable` turns *"what if the alert reaches nobody and how would we know"* — the question that started this entire review — from an unanswerable worry into an audit event, a metric, and a line in the after-action report.

Two things still decide this build, both unchanged since v2.0 and both scheduled: **hold the freeze on 21 August**, and **when a day runs long, cut from the written list in Part 16 rather than negotiating at 1 a.m.** Everything else in these thirty-six parts is execution.

---

---

# PART 37 — **[v3.0] BOOTSTRAP: THE FILES A TEAMMATE ACTUALLY RUNS**

`make demo` appears twice in this document's Definition of Done (Part 19: *"`git clone && make demo` works on a fresh laptop"*) and was **never defined anywhere.** A gate that references an undefined command is not a gate. Part 37 is every file a teammate runs, in full — modelled on the same `setup / doctor / demo` idiom the sibling PRAVESH project already uses, so the two repos feel like one team's work.

## 37.1 `Makefile`

```makefile
.PHONY: help setup setup-ml doctor db-up db-migrate seed data demo api web worker check test clean
.DEFAULT_GOAL := help

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ─────────────────────────── setup ───────────────────────────
setup: ## venv + backend deps + both frontends + pre-commit hooks
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	cd web/console && npm ci
	cd web/citizen && npm ci
	$(VENV)/bin/pre-commit install
	@test -f .env || (cp .env.example .env && \
	  echo "→ .env created from template. Fill it in, then run 'make doctor'.")

setup-ml: ## ML service deps — for the HF Space only, NOT for services/api (Part 22)
	$(PIP) install -r services/ml/requirements-ml.txt
	@echo "⚠  These belong on the HF Space. services/api must never import torch."

secrets: ## Generate the two v3.0 secrets (Part 25) — run ONCE, then share via the team vault
	@echo "PHONE_HASH_PEPPER=$$($(PY) -c 'import secrets;print(secrets.token_urlsafe(32))')"
	@echo "ALERT_SIGNING_SEED_B64=$$($(PY) -c 'import base64,nacl.signing as s;\
	  print(base64.b64encode(bytes(s.SigningKey.generate())).decode())')"
	@echo "ALERT_SIGNING_PUBKEY_B64=  ← derive with scripts/derive_pubkey.py, then put it"
	@echo "   in web/citizen/.env as VITE_ALERT_SIGNING_PUBKEY_B64 (public by design, §1.5.3)"

# ─────────────────────────── database ───────────────────────────
db-up: ## Start local Postgres+PostGIS, Redis, MailHog
	docker compose -f infra/docker-compose.yml up -d
	@$(PY) scripts/wait_for_db.py

db-migrate: ## Apply migrations 0001→0012 against the DIRECT url (Part 23)
	$(VENV)/bin/alembic -x db_url=$$DATABASE_URL_DIRECT upgrade head

db-reset: ## Nuke and rebuild local state. Refuses if DATABASE_URL_DIRECT is not localhost.
	@$(PY) scripts/guard_local_only.py
	docker compose -f infra/docker-compose.yml down -v
	$(MAKE) db-up db-migrate seed

seed: ## Apply every data/seeds/*.sql in lexical order (Rule 3)
	@for f in data/seeds/*.sql; do echo "→ $$f"; \
	  psql "$$DATABASE_URL_DIRECT" -v ON_ERROR_STOP=1 -f "$$f"; done
	@$(PY) scripts/verify_seeds.py   # asserts app_config ≥ 74 rows, capability = 8 rows

data: ## Download + load every external dataset (§1.6.2) incl. the basemap (§1.6.5). Slow. Run once.
	bash scripts/fetch_data.sh          # includes the pmtiles extract — the demo needs it offline
	$(PY) scripts/load_population.py --level 3
	$(PY) scripts/load_population.py --level 5
	$(PY) scripts/load_towers.py
	$(PY) scripts/load_safe_zones.py --area IN

# ─────────────────────────── run ───────────────────────────
api:    ## FastAPI on :8000
	$(VENV)/bin/uvicorn services.api.main:app --reload --port 8000
worker: ## Delivery worker (Redis Streams consumer)
	$(PY) -m services.delivery.worker
ingest: ## Ingestion scheduler (APScheduler)
	$(PY) -m services.ingestion.scheduler
web:      ## Ops console on :5173
	cd web/console && npm run dev
web-citizen: ## Citizen PWA on :5174
	cd web/citizen && npm run dev

# ─────────────────────────── the demo ───────────────────────────
demo: ## THE GATE (Part 19). Loads the frozen snapshot and serves everything OFFLINE.
	@$(PY) scripts/guard_local_only.py
	$(MAKE) db-up db-migrate
	$(PY) scripts/load_snapshot.py --latest    # all 22 tables (§15)
	$(PY) scripts/verify_snapshot.py --strict  # fails if any screen would render zeroes
	@echo ""
	@echo "  ✔ Snapshot loaded. Console :5173 · Citizen :5174 · API :8000"
	@echo "  ✔ No network calls required from here. Unplug the cable and re-check."
	@echo ""
	$(VENV)/bin/honcho -f infra/Procfile.demo start

# ─────────────────────────── quality ───────────────────────────
doctor: ## Report exactly what this machine can and cannot run
	@$(PY) scripts/doctor.py

check: ## Everything CI runs
	$(VENV)/bin/ruff check services/
	$(VENV)/bin/mypy services/delivery services/ml services/governance services/response
	$(VENV)/bin/pytest tests/unit --cov=services/delivery --cov-fail-under=95
	$(VENV)/bin/pytest tests/property tests/contract tests/integration
	$(PY) scripts/check_no_hardcoding.py
	$(PY) scripts/check_env_example.py
	$(PY) scripts/check_channel_capability.py
	cd web/console && npm run test:contrast
	npx playwright test

test:
	$(VENV)/bin/pytest -q

snapshot: ## Freeze current DB state as a committed demo fixture
	$(PY) scripts/snapshot.py --out data/snapshots/$$(date +%Y-%m-%d).json
	@echo "→ Commit it. This is what the demo runs from."
```

**`make demo` runs `verify_snapshot.py --strict` before starting anything.** That is the single most valuable line in this Makefile: it is Risk #20's mitigation made unavoidable. A snapshot missing `delivery_event` or `citizen_response` fails the command **on your laptop, days early** — rather than rendering a Command Board full of zeroes on stage.

**`db-reset` and `demo` both call `guard_local_only.py`** — a six-line script that refuses to run if `DATABASE_URL_DIRECT` does not point at localhost. `make db-reset` against the Neon demo database on 23 August would be an unrecoverable, entirely preventable mistake.

## 37.2 `scripts/doctor.py` — the honesty tool

Borrowed wholesale from PRAVESH's idiom: **report what this machine can run, never guess and never silently skip.**

```python
#!/usr/bin/env python3
"""scripts/doctor.py — what can this laptop actually do?

Prints a capability report. Never fails the build; its whole job is to make
"works on my machine" impossible to say by accident. Run it on all six laptops
on Day 4 and paste the output in the team channel.
"""
import importlib.util, os, shutil, socket, sys

def has_module(name): return importlib.util.find_spec(name) is not None
def has_bin(name):    return shutil.which(name) is not None
def env(name):        return bool(os.environ.get(name))

def tcp(host, port):
    try:
        with socket.create_connection((host, port), timeout=2): return True
    except OSError: return False

CHECKS = [
    ("python 3.11+",            sys.version_info >= (3, 11),          "required"),
    ("postgres reachable",      tcp("localhost", 5432),               "make db-up"),
    ("redis reachable",         tcp("localhost", 6379),               "make db-up"),
    ("psql client",             has_bin("psql"),                      "needed by 'make seed'"),
    ("ogr2ogr (GDAL)",          has_bin("ogr2ogr"),                   "needed by 'make data' §1.6.2"),
    ("aws cli",                 has_bin("aws"),                       "needed for the DEM check, Part 29"),
    ("node + npm",              has_bin("npm"),                       "frontends"),
    ("docker compose",          has_bin("docker"),                    "local infra"),
    # ── secrets: absence is a HARD stop for specific features, named explicitly ──
    ("DATABASE_URL_POOLED",     env("DATABASE_URL_POOLED"),           "app runtime, Part 23"),
    ("DATABASE_URL_DIRECT",     env("DATABASE_URL_DIRECT"),           "migrations only, Part 23"),
    ("PHONE_HASH_PEPPER",       env("PHONE_HASH_PEPPER"),             "migration 0012 FAILS without it, Trap 11"),
    ("ALERT_SIGNING_SEED_B64",  env("ALERT_SIGNING_SEED_B64"),        "B10 peer relay cannot sign, Rule 11"),
    ("TWILIO_ACCOUNT_SID",      env("TWILIO_ACCOUNT_SID"),            "SMS + IVR + human relay"),
    ("FCM_SERVICE_ACCOUNT_JSON",env("FCM_SERVICE_ACCOUNT_JSON"),      "push, the PRIMARY channel"),
    ("OPENCELLID_TOKEN",        env("OPENCELLID_TOKEN"),              "optional — Part 30's 5-feature fallback applies"),
    # ── ML: only needed on the HF Space, and it is CORRECT for these to be absent locally ──
    ("torch (ML service only)", has_module("torch"),                  "HF Space only — absent here is CORRECT (Part 22)"),
    ("nacl (signing)",          has_module("nacl"),                   "required on the API service"),
    ("basemap .pmtiles present", os.path.exists("web/console/public/tiles/setu-basemap.pmtiles"),
                                                                          "make data — WITHOUT IT THE MAP IS BLANK OFFLINE, §1.6.5"),
]

def main() -> int:
    width = max(len(n) for n, _, _ in CHECKS)
    print("\nSETU doctor — what this machine can run\n" + "─" * (width + 30))
    for name, ok, note in CHECKS:
        print(f"  {'✔' if ok else '✘'}  {name:<{width}}  {'' if ok else '← ' + note}")
    print("\nNothing above is required for the whole system to run. Absent capabilities")
    print("degrade named features honestly — they never make the platform guess.\n")
    return 0   # deliberately never non-zero: this is a report, not a gate

sys.exit(main())
```

**`torch` absent locally is printed as *correct*, not as a failure.** That one line prevents the most likely Day-4 confusion on this project: a teammate installing PyTorch into the API service to "fix" a red check, and quietly re-creating the exact 512 MB OOM topology Part 22 exists to prevent.

## 37.3 `infra/docker-compose.yml`

```yaml
# Local development ONLY. The demo environment is Neon + Upstash (Part 15).
# Local Redis is unlimited — which is why v2.1 made "dev uses local Redis"
# a rule rather than a preference (§1.4: one afternoon of testing against
# Upstash can burn a whole day's 16,600-command budget).
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: setu
      POSTGRES_PASSWORD: setu
      POSTGRES_DB: setu
    ports: ["5432:5432"]
    volumes: ["setu_pg:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U setu"]
      interval: 5s
      retries: 12

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports: ["6379:6379"]
    volumes: ["setu_redis:/data"]

  mailhog:                      # captures Brevo-bound email locally, no quota spend
    image: mailhog/mailhog
    ports: ["1025:1025", "8025:8025"]

volumes:
  setu_pg:
  setu_redis:
```

The image is **`postgis/postgis:16-3.4`, not plain `postgres`** — PostGIS, `pgcrypto` and `pg_trgm` all need to be present before migration `0001` runs, and a plain Postgres image fails on the first `CREATE EXTENSION postgis` in a way that reads like a permissions problem.

## 37.4 `.env.example` — the file `check_env_example.py` diffs against Part 25

```bash
# ══ SETU .env.example ══  Every key in Part 25's table appears here, with a
# placeholder and never a real value. CI fails the build if the two drift.

# ── Database (Part 23: two URLs, not one) ──
DATABASE_URL_POOLED=postgresql+asyncpg://setu:setu@localhost:5432/setu
DATABASE_URL_DIRECT=postgresql://setu:setu@localhost:5432/setu

# ── Pool sizing: ENV, not app_config. You cannot read a config table before you have
#    a pool to read it with. This is the documented bootstrap exception (Part 38). ──
DB_POOL_SIZE=10
DB_POOL_MAX_OVERFLOW=5
DB_POOL_TIMEOUT_S=10

# ── Redis (local for dev, ALWAYS — §1.4) ──
REDIS_URL=redis://localhost:6379/0
REDIS_NAMESPACE=setu:v1

# ── Channels ──
FCM_SERVICE_ACCOUNT_JSON=./secrets/fcm-service-account.json   # gitignored
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WEBHOOK_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_FROM_NUMBER=+15005550006
BREVO_API_KEY=xkeysib-xxxxxxxx

# ── v3.0 secrets — READ Part 25's rotation notes before touching either ──
# Rotating PHONE_HASH_PEPPER invalidates every phone_hash: it is a MIGRATION, not an env swap.
PHONE_HASH_PEPPER=generate-with-make-secrets
# Rotating the signing seed requires shipping a new PWA bundle: it is a RELEASE.
ALERT_SIGNING_SEED_B64=generate-with-make-secrets

# ── ML service (Part 22 — api must NEVER import torch) ──
HF_SPACE_URL=https://your-space.hf.space
INTERNAL_ML_KEY=generate-a-long-random-string

# ── Platform ──
JWT_SIGNING_SECRET=generate-a-long-random-string
WEBHOOK_HMAC_SECRET=generate-a-long-random-string
SENTRY_DSN=
SENTRY_ENABLED=true          # set false during Locust runs (Part 28)
OPENCELLID_TOKEN=            # empty is OK — Part 30's 5-feature fallback applies
PUBLIC_BASE_URL=http://localhost:8000
SLACK_OR_DISCORD_ALERT_WEBHOOK=
```

```bash
# web/citizen/.env — build-time, and this one IS public by design (§1.5.3)
VITE_API_BASE=http://localhost:8000
VITE_ALERT_SIGNING_PUBKEY_B64=paste-the-derived-public-key
```

## 37.5 `infra/render.yaml` and `infra/vercel.json`

```yaml
# infra/render.yaml — API only. NO torch, NO transformers (Part 22).
services:
  - type: web
    name: setu-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn services.api.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health          # also the keepalive.yml target (Part 15)
    envVars:
      - key: DATABASE_URL_POOLED
        sync: false
      - key: PHONE_HASH_PEPPER
        sync: false
      - key: ALERT_SIGNING_SEED_B64
        sync: false
      # …every remaining key from Part 25, all sync:false
```

```json
// infra/vercel.json — Hobby tier, non-commercial (§1.1)
{
  "buildCommand": "cd web/console && npm run build",
  "outputDirectory": "web/console/dist",
  "rewrites": [{ "source": "/api/(.*)", "destination": "https://setu-api.onrender.com/api/$1" }],
  "headers": [{
    "source": "/(.*)",
    "headers": [
      { "key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains" },
      { "key": "X-Content-Type-Options",    "value": "nosniff" },
      { "key": "Content-Security-Policy",
        "value": "default-src 'self'; connect-src 'self' https://setu-api.onrender.com; img-src 'self' data: https://*.basemaps.cartocdn.com; script-src 'self'; style-src 'self' 'unsafe-inline'" }
    ]
  }]
}
```

The CSP has **no `unsafe-inline` on `script-src`** — which is the control that makes C6's free-text "Other" field safe against stored XSS regardless of any rendering mistake (§12.1, surface 5).

## 37.6 The 15-minute onboarding path

What a teammate runs, in order, on Day 4. **Anything that fails here fails on a laptop, days before it could fail on stage.**

```bash
git clone <repo> && cd setu
make setup            # venv, deps, hooks, .env from template
make secrets          # → paste the two v3.0 values into .env, share via the team vault
make db-up            # Postgres+PostGIS + Redis + MailHog
make db-migrate       # 0001 → 0012.  FAILS LOUDLY if PHONE_HASH_PEPPER is missing (§5.13)
make seed             # every data/seeds/*.sql;  verify_seeds.py asserts the row counts
make doctor           # ← paste this output in the team channel. All six of us.
make check            # everything CI runs, locally, before the first push
make data             # slow, once: §1.6.2's downloads  (skippable if using a snapshot)
make demo             # the Part 19 gate. Then UNPLUG THE CABLE and re-check.
```

**`make demo` is the acceptance test for this entire document.** If it works on a fresh laptop with the network unplugged, every claim in Parts 0–36 is reproducible by someone who was not in the room when it was written — which is the only definition of "no loose ends" that actually means anything.

---

---

# PART 38 — **[v3.0] THE TWO AUDITS: NOTHING HARDCODED, EVERYTHING REAL**

Two claims run through this entire document, and both are the kind that are easy to assert and hard to keep. This part is the evidence for each, produced by **actually auditing the spec rather than restating the rule** — which is why it opens by listing five places where the spec violated its own Rule 1 and had to be fixed.

---

## 38.1 The hardcoding audit — five violations found in this document, and fixed

A self-audit of every code sample in Parts 0–37 found five literals sitting in decision positions. Each is listed with what it was, why it mattered, and what replaced it. **None of these would have been caught by `check_no_hardcoding.py`** — three were in SQL, one in TypeScript, one in an XML template, and the script only walks Python ASTs. That is itself the finding: *a linter guards one language, and this system is written in four.*

| # | Where | The violation | Why it mattered | Fixed to |
|---|---|---|---|---|
| **A** | `HumanRelayAdapter.send()` (§8.6) | `ORDER BY CASE kind WHEN 'panchayat' THEN 1 …` — the relay-node priority order baked into a SQL `CASE`, with a comment promising "from config in prod" | **Part 21 already seeded `relay.node_kind_priority` and nothing read it.** A config row that no code path reads is worse than no config row: it looks like compliance | `ORDER BY array_position($2::text[], kind)` with the array supplied from `app_config` |
| **B** | `v_reachability` view (§5.12) | `assurance_level(d.id) >= 2` and `>= 4` — the tier floors for "reached" and "acknowledged" as literals in the view body | This is **the** number in the pitch. Whether provider-acceptance counts as "reached" is a *policy* decision that changes the headline figure, and it was buried in a view where nobody would ever question it | A `cfg` CTE reading `reachability.reached_tier_floor` / `acknowledged_tier_floor`, each with a `note` explaining why tier 1 is deliberately **not** "reached" |
| **C** | `services/api/db.py` (Part 23) | `pool_size=10, max_overflow=5, pool_timeout=10` | Real tunables against a free-tier connection ceiling — and the exact three numbers Part 13's load test exists to validate | Env vars `DB_POOL_SIZE` / `DB_POOL_MAX_OVERFLOW` / `DB_POOL_TIMEOUT_S`. **Env, not `app_config`** — see the bootstrap exception below |
| **D** | `web/citizen/src/relay.ts` (§8.7) | BLE chunk size implied by a `~512` comment, with no configurable value | Different Android Bluetooth stacks negotiate different MTUs. This value **will** be tuned on the two real demo devices during rehearsal — a literal would mean a code change and a redeploy on Day 12 | `CFG.relayChunkBytes` ← `relay.peer_chunk_bytes` = 480 |
| **E** | The relay TwiML template (§8.6) | `numDigits="1" timeout="10"` typed into the XML | Ten seconds is a **UX decision about a stressed human on a phone during a disaster.** That is precisely the class of number that should be tunable after hearing one real call | Interpolated from `ivr.gather_digits` / `ivr.gather_timeout_s` |

**Consequence: `check_no_hardcoding.py` is extended to a second and third pass.** A Python-only AST walker cannot see three of the five violations above.

```python
# scripts/check_no_hardcoding.py — [v3.0] Part 38: three passes, not one.
#
# Pass 1 (v2.1): Python AST — bare numeric literals in Compare/BinOp inside guarded dirs.
# Pass 2 (NEW): SQL — numeric literals on the right-hand side of a comparison inside
#   data/seeds/*.sql VIEW bodies and migrations/*.py. Catches violation B.
#   Allowlist: 0, 1, 100 (percentage arithmetic), and anything inside a `-- config-exempt:` line.
# Pass 3 (NEW): TS/TSX — numeric literals in comparisons or as function arguments in
#   web/*/src/{relay,verify,response}.ts*. Catches violation D.
#
# Templates (TwiML, email) are covered differently: a test asserts that every
# generated TwiML document contains NO literal digits outside {{...}} placeholders.
# That is what catches violation E, and a linter could not have.
SQL_GUARDED   = ["data/seeds", "migrations"]
TS_GUARDED    = ["web/citizen/src", "web/console/src/components"]
TEMPLATE_TEST = "tests/unit/test_twiml_has_no_literals.py"
```

### The rule that separates a threshold from a protocol constant

Rule 1 says no magic values. Taken absolutely it is incoherent — `sha256` has a fixed output length, an enum has fixed ordinals, and JSON has fixed syntax. So the working rule, applied throughout this document:

> **A value goes in config if changing it changes *behaviour someone could reasonably want different*. A value stays in code if changing it changes *what the thing is*.**

By that test, these eight literals **legitimately remain in code**, and each is listed so a reviewer never has to wonder whether it was an oversight:

| Literal | Where | Why it stays |
|---|---|---|
| `LEGAL: dict[State, frozenset[State]]` | `state_machine.py` (§7.1) | **A correctness invariant, not a tunable.** Making `sent → acknowledged` legal via a config row would let an `UPDATE` corrupt the delivery model. v2.1 called this "declared as data"; the data belongs in code, under test |
| `CANONICAL_FIELDS` tuple | `alert_signing.py` (§8.7) | **The signature format itself.** If this were config, a config change would silently invalidate every signature ever issued and every PWA bundle in the field. It is a wire protocol |
| `assurance_event` enum ordinals 0–5 | `assurance_level()` (§5.7) | **The ladder's definition.** The *floors* that read it are config (violation B); the ordering of evidence strength is what the ladder *is* |
| `ALLOWED_LITERALS = {0, 1, -1, 2, 100}` | `check_no_hardcoding.py` | The linter's own allowlist. Short, and **every exception is a reviewed line in that file** (Part 32) |
| `GUARDED_DIRS`, `SQL_GUARDED`, `TS_GUARDED`, `SNAPSHOT_TABLES` | CI scripts, `snapshot.py` | **Repository structure**, not runtime behaviour. Putting them in the database would mean a CI script needs a database to know what to check |
| FCM message JSON shape | `FcmAdapter.send()` (§8.3) | Google's wire format. Not ours to tune |
| HTTP status codes (`304`, `403`, `409`, `422`) | Adapters, routers (Part 10) | RFC-defined. The **status-code contract table** in Part 10 is the reviewable artifact |
| `sys.version_info >= (3, 11)` | `doctor.py` (§37.2) | A hard platform requirement, not a preference |

### The one documented bootstrap exception

**Pool sizing (violation C) went to environment variables, not to `app_config`, and that is deliberate:** you cannot read a config table before you have a connection pool with which to read it. Anything required *to establish the database connection itself* must come from the environment. That is exactly three values (`DB_POOL_SIZE`, `DB_POOL_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_S`) plus the connection URLs, all in `.env.example` and all covered by `check_env_example.py`. **Recorded here so nobody "fixes" it into `app_config` and creates a circular dependency that fails at startup with an unhelpful error.**

---

## 38.2 The reality audit — every number in the product, classified

"Everything should be real" is a stronger requirement than "nothing hardcoded," and it needs a taxonomy, because a system that only ever displayed directly-measured facts could not show a percentage. Every figure the product renders falls into exactly one of five classes. **Four are legitimate. The fifth is a bug.**

| Class | Meaning | Rendered as | Examples |
|---|---|---|---|
| **① MEASURED** | Came from outside us, or from a provider we do not control. Carries `source_id` + `fetched_at` + `checksum` (Rule 4) | Plainly | USGS/GDACS events · Open-Meteo CAPE · WorldPop population · Copernicus terrain · OpenCelliD towers · OSM shelters · **FCM message IDs · Twilio carrier delivery receipts · `CallStatus=in-progress` · DTMF keypresses** |
| **② DERIVED** | Computed from ① by a formula that is *published*, with its inputs stored (Rule 10) | Plainly, with the breakdown available | Reachability % · assurance level · vulnerability factors · assistance priority (+ `priority_factors`) · lead time (+ `coverage_pct`) · reach-risk score (+ `features`) |
| **③ OURS, SEEDED** | Our own design decisions, in `data/seeds/*.sql`, reviewable in git | Plainly, and published on `/methodology` | 36 v3.0 config thresholds · escalation policy · `channel_capability` reasons · relay-node registry |
| **④ SIMULATED, BADGED** | Deliberately not real, and **visibly labelled at every surface** | With a badge, in DB *and* UI | `simulated=true` SMS → `SIM` chip · bootstrap reach-risk → `BOOTSTRAP` chip · human relay → `HUMAN` chip · peer relay → `⇄ PEER` chip · `authoritative_source` approval → `AUTO-AUTH` chip |
| **⑤ FABRICATED** | A number with no measurement, no published derivation, and no badge | **Never. This class must be empty** | — |

### What class ⑤ being empty actually cost — the five things we refused to show

This is the part that makes the claim checkable rather than rhetorical. Each of these could have been faked convincingly, and each was declined **with the refusal recorded in the database** so it survives into the methodology endpoint and the PDF report:

| We could have shown | We show instead | Where the refusal lives |
|---|---|---|
| SMS "opened" ~88% | **Struck through: "no mobile carrier exposes SMS read receipts to the sender"** | `channel_capability.not_applicable_reason` (§8.2) |
| Email open rate | **Struck through, with the reason we declined a signal we could have built:** a tracking pixel is a privacy intrusion *and* unreliable — a blocked pixel is indistinguishable from an unopened email | Same table |
| Siren "delivered" | **Struck through: a physical broadcast produces no receipt of any kind.** Only B9's human confirmation closes it | Same table |
| Earthquake warning lead time | **Excluded, with `coverage_pct` published**: a quake is detected *after* it happens; there is no forecast onset to measure against | `v_lead_time_coverage` (§5.12) |
| Live shelter capacity, live road closures, learned per-channel reliability | **Not built.** No free live source exists for the first two; the third needs traffic volume we will not have by demo day | Part 35, with the reason on each row |

### The two places where "real" is bounded, stated without softening

1. **Two of ~340 units carry real SMS.** The Twilio trial reaches verified numbers only; TRAI DLT registration needs a legal entity and ten business days (Trap 5). Everything else runs the *identical* engine, state machine, retry and escalation against `SimulatedCarrierAdapter` — flagged `simulated=true` in the database and badged `SIM` on screen. Said aloud in §8.5's verbatim pitch language.
2. **The relay nodes are real institution types with our own phones behind them** (§4.7). Cold-calling an actual panchayat office during a hackathon demo would be indefensible. The workflow, the audit trail and the privacy design are exactly what deployment would use; only the number differs — the same boundary, drawn the same way, as the SMS one.

### The mechanical guards that keep class ⑤ empty

Not one of these is a convention someone has to remember:

- `check_channel_capability.py` — build fails if an adapter claims a tier its table row denies (Rule 8)
- `test_no_channel_reports_unsupported_tier` — property test over every channel × tier combination
- `CHECK (location IS NULL OR location_consent = true)` — the privacy promise as a constraint (§5.8)
- `assistance_case.priority_factors NOT NULL` — a score cannot exist without its inputs (Rule 10)
- `CHECK (version_number = 1 OR change_reason IS NOT NULL)` — a version bump cannot exist without a stated reason
- `alert_one_active_per_incident_uix` — two contradictory live warnings are a database error, not an ambiguity
- `UNIQUE (alert_id, approver_id)` — one officer cannot be two pairs of eyes
- `audit_immutable` trigger — the ledger cannot be edited, by us or anyone
- `test_snapshot_completeness.py` — a demo screen cannot silently render zeroes
- `verify_seeds.py` — asserts 74 `app_config` rows and 8 capability rows before anything runs

**Ten guards, all in CI or in Postgres, none of them a habit.** That is the whole answer to both halves of the question: the thresholds are in config because a linter and a seed-verifier fail the build otherwise, and the numbers are real because the database refuses to store a decision without its inputs and CI refuses to ship a channel that overclaims.

---

## One-line product positioning

> **SETU is not another disaster alerting system. It is the assurance layer that determines whether a warning was authorized, delivered, understood, answered, and acted on — and it is honest, in public, about every one of those it cannot prove.**

---

*End of SETU_MASTER_v3.0_MERGED. 40 parts · 42 features · 28 core · 8 new tables · 3 views · 6 migrations · 36 new config rows · 13 constitution rules · 13 traps · 23 risks · 20 rejected-with-reasons · full stack in §1.5 · every data source in §1.6 · runnable bootstrap in Part 37 · 5 self-audit violations found and fixed in Part 38 · 10 mechanical guards. Every dependency free-tier or open-source. ₹0.*
