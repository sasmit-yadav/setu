# Starting SETU

Two ways to run this. Pick one and stick to it for a session — mixing them is
how you end up looking at an empty desk and blaming the code.

- **Cloud data plane** (what the demo uses): Neon + Upstash hold the data, every
  process runs on this laptop against them. Nothing needs Docker except the
  translator.
- **Fully local**: Postgres and Redis in Docker on this machine. Good for tests
  and for working offline.

Every command is `python run.py <task>`; `python run.py` on its own lists them.

---

## Cloud data plane — the demo path

Five terminals. The first four stay open.

```powershell
$env:PYTHONIOENCODING = "utf-8"     # or a Malayalam headline kills the process
```

| # | Command | What it is | Port |
|---|---|---|---|
| 1 | `python run.py ml-docker` | IndicTrans2 translator, in Docker | 8001 |
| 2 | `python run.py api-cloud` | API against Neon + Upstash | 8000 |
| 3 | `python run.py worker-cloud` | the process that actually sends | — |
| 4 | `python scripts/siren_listener.py` | stands in for the panchayat siren | 9099 |
| 5 | `python run.py console-dev` | officer desk | 5173 |

Optional alongside: `python run.py ingest-cloud --watch` keeps USGS and GDACS
polling, and `python run.py citizen-dev` serves the citizen app on 5174.

Then check, in this order:

```powershell
python scripts/siren_listener.py --test    # hear it once, before an audience
python scripts/preflight_demo.py           # 32 read-only checks
```

Sign in at <http://localhost:5173> as `vythiri.a@setu.example` (and
`vythiri.b@setu.example` in a second browser profile — Two-Eyes needs two
distinct officers).

### Why the local console and not the hosted one

Render cannot reach this laptop's `:8001`, so composing on
setuconsole.vercel.app leaves a brand-new headline untranslated and the Kerala
quality gate blocks the Send. The local desk proxies `/api` to whatever is on
`:8000`, which is `api-cloud`, which *can* reach the translator. Compose here.

---

## Fully local

```powershell
python run.py db-up            # Postgres 5433, Redis 6379, MailHog 8025
python run.py data-bootstrap   # migrate + config + enrollment + verify
python run.py api              # :8000 against local Postgres
python run.py worker           # local Redis consumer
python run.py console-dev      # :5173
```

`python run.py test` needs this stack up. Without it most of the suite skips and
the RBAC and retry tests fail on `ConnectionRefused` — that is the environment,
not the code.

---

## First time on a machine

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
python run.py setup            # writes .env from the template
python run.py secrets          # generates the pepper, Ed25519 pair, JWT secrets
python run.py doctor           # says what this machine can and cannot run
```

`.env.cloud` (Neon, Upstash, channel credentials) is not generated — copy it
from whoever has it. `run.py *-cloud` refuses to fall back to `.env`, on purpose:
silently draining the local queue while you believe you are draining production
is the worst outcome of a typo.

The translator needs `HF_TOKEN` in `.env`. `ai4bharat/indictrans2-en-indic-dist-200M`
is a gated repo, so without an accepted licence and a token the first load 403s
and `/translate` answers `models_absent`.

---

## The translator, in more detail

`IndicTransToolkit` ships a Cython extension with no Windows wheel, so pip has
to compile it and that needs MSVC build tools. The Dockerfile is the same image
the Hugging Face Space uses and it compiles on Linux, which makes the container
the ordinary path here rather than a workaround.

```powershell
python run.py ml-docker              # build if needed, else start
python run.py ml-docker --rebuild    # force a fresh image
curl http://127.0.0.1:8001/health    # want toolkit: true
```

The model weights (~1.1 GB) live in the `setu-hf-cache` Docker volume, so
recreating the container costs nothing. `docker start setu-ml` is enough on a
normal morning.

---

## Things that will waste your time otherwise

- **`uvicorn --reload` does not pick up changes on Windows here.** Edit backend
  code, see nothing happen, restart `api-cloud` by hand.
- **Session tokens last 15 minutes.** A desk showing frozen numbers is usually an
  expired token silently 401ing on every refresh. Sign out and back in.
- **The Docker daemon must be up before `ml-docker`.** It checks now and says so,
  rather than mistaking a dead daemon for a missing image and rebuilding.
- **The first page load waits on the map query**, which is the slowest call —
  around twenty seconds against Neon. Press Refresh once; do not debug it.
- **Render free sleeps after 15 idle minutes.** Hit `/health` before anyone sits
  down or the first request takes ~50 s.
- **Renaming an `app_config` key leaves the old row behind.** `seed-config`
  upserts and never prunes. Delete the old key by hand.

---

## Ports

| Port | What |
|---|---|
| 5173 | officer console (dev) |
| 5174 | citizen PWA (dev) |
| 8000 | API — `api` or `api-cloud` |
| 8001 | translator |
| 9099 | siren listener |
| 5433 | local Postgres (Docker) |
| 6379 | local Redis (Docker) |
| 8025 | MailHog UI (Docker) |

## Checks worth knowing

```powershell
python scripts/preflight_demo.py        # is the demo going to work right now
python scripts/demo_readiness.py        # roadmap claims vs the live system
python scripts/check_orphan_config.py   # config seeded but read by nothing
python run.py check                     # everything CI runs
```
