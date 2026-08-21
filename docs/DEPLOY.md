# Deploying SETU

Four free-tier services, one repo. Total cost **₹0**.

```
Vercel  ──  citizen PWA (HTTPS, static)      ─┐
Render  ──  API + delivery worker             ├─ Neon (Postgres+PostGIS)
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

> **The SPA rewrite matters.** `vercel.json` deliberately excludes `/sw.js`,
> `/registerSW.js`, `/manifest.webmanifest`, `/icon-*` and `/assets/*` from the
> catch-all. A naive rewrite returns `index.html` for `/sw.js`, which then
> registers as an HTML document and dies — the same class of failure that
> silently killed the dev service worker for the whole build.

---

## 4. Prove it, don't assume it

Run these in order. Each one is a roadmap exit-gate criterion.

```bash
# API is up and talking to Neon
curl -s https://<api>/health

# The Firebase block reaches the browser (else "Enable alerts" never appears)
curl -s https://<api>/api/v1/public/config | grep firebase

# The Space is awake and loaded
curl -s https://<space>/health
```

Then on the **presenting Android phone**, in Chrome:

1. Open the Vercel URL, sign in, tap **Enable alerts on this phone**, grant the
   prompt. This should be the first ever real FCM token.
2. Confirm it landed:
   ```sql
   SELECT id, unit_id, push_token IS NOT NULL FROM recipient
   WHERE kind = 'citizen_pwa';
   ```
3. Dispatch an alert, then check the ladder actually advanced past rung 1 —
   this is the row that has never existed:
   ```sql
   SELECT event_type, source FROM delivery_event
   WHERE source IN ('fcm_send', 'service_worker') ORDER BY id DESC LIMIT 5;
   ```
   `fcm_send` proves the send; `service_worker` proves the phone called home.
4. **Install the PWA** (⋮ → Add to home screen), then put the phone in
   airplane mode and reopen it. The alert must still render — Gate 3.

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

- **B10 peer relay.** No shipping browser exposes the GATT *peripheral* role,
  so phone-to-phone through two PWA tabs may be impossible (`IMPLEMENTATION.md`
  §8.1). Spike it for 20 minutes on two Androids **before** budgeting any
  engineering time; the cut order already pre-authorises dropping it.
- **Nationwide real SMS.** Needs TRAI DLT registration — a registered legal
  entity and ~10 business days. Every simulated delivery is flagged
  `simulated = true` and badged `SIM`; the engine, state machine and escalation
  are identical on both paths.
