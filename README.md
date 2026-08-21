---
title: SETU ML
emoji: 🛰️
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# SETU

**The layer that proves a disaster warning arrived.**

On 29 July 2024 an NGO warned a district office sixteen hours before the
Wayanad landslide. 231 people died. The collector's office says it never
received the warning, and nobody could prove otherwise — because nothing was
recording.

India predicts disasters reasonably well. It fails in the last fifty
kilometres: the human handoff from NGO to district to village officer, which
has no instrumentation at all. SETU is the layer underneath the national
broadcast, not a competitor above it. SACHET can tell a billion people a
disaster is coming; it cannot tell you whether one of them heard it, who
authorised it, or what happened to the person who could not get out.

## The frontmatter above

This repository doubles as the source for the **SETU ML Hugging Face Space**
(Part 22). The root `Dockerfile` builds `services/ml` only — the translation
and embedding service — because it is the one component that needs PyTorch, and
`services/api` must never import it. `scripts/check_no_torch.py` enforces that
in CI.

Everything else in this repo is the API, the delivery engine, the operations
console and the citizen PWA, none of which the Space builds or runs.

## Documentation

| Read this | For |
|---|---|
| `docs/TASK.md` | What to do next, and what is blocked on what |
| `docs/IMPLEMENTATION.md` | How it actually works, and every deviation from the spec |
| `docs/PART19-DOD.md` | The Definition of Done, walked line by line with evidence |
| `docs/SETU_MASTER_v3.0_MERGED.md` | The design specification (42 features, 38 parts) |
| `docs/evidence/` | Dated artifacts — captured backoff curves, etc. |

## Running it locally

```bash
python run.py db-up          # Postgres+PostGIS on :5433, Redis on :6379
python run.py data-bootstrap # migrate, seed config, verify
python run.py api            # :8000
python run.py worker         # delivery consumer
python run.py citizen-dev    # citizen PWA on :5174
```

The operations console is `:5173`. `python run.py demo` is the Part 19 gate:
it loads the frozen snapshot and proves it is not empty.

## The idea in one table

Most systems would show you "88% delivered". SETU shows a six-rung assurance
ladder where capability is **data, not code** — and where a channel genuinely
cannot prove a rung, the UI strikes it through and prints the reason:

> No carrier on earth gives a sender an SMS read receipt. We could have shown
> you 88%. We show you what we can prove.
