# Redis command budget — re-derived after B3 — 21 Aug 2026

Part 19: *"Redis command budget has ≥5× headroom for demo day."* Part 1.4
re-derives this at ~305–310 commands per full alert run and names the Part 28
80% threshold (13,280/day of a 500,000/month ≈ 16,600/day budget) as **"the
primary guard, not a nice-to-have."** Never measured until now, and B3 (this
session) changed the model in a way Part 1.4 did not anticipate.

## What B3 actually added, measured against the real database

Part 1.4's table costs every new v3.0 feature at 0–2 commands **per alert
run**. B3's retry/escalation writer does that too — but it also added a
`ZPOPMIN` call to `drain_due_retries()`, invoked on **every worker loop tick**,
independent of whether any alert has been dispatched. That is a cost that
scales with *wall-clock time the worker is running*, not with alert volume,
which is a new axis Part 1.4's model never had to account for.

**Per-alert-run cost, from real data** (33 real `alert.dispatched` events, not
assumed):

| Metric | Count | Rate |
|---|---|---|
| `delivery.retry_scheduled` events | 28 | **0.848 ZADD per dispatch** |
| `delivery.channel_escalated` events | 22 | **0.667 ZADD per dispatch** |

So each real dispatch now costs the spec's ~310 baseline **plus ≈1.5 ZADDs**,
not the 0–1 the original table assumed — a small, absorbable addition on its
own.

**Per-tick idle cost, from the code, not a run:** `due_delivery_ids()` issues
at least one `ZPOPMIN` per call even when the retry set is empty (it breaks on
the first empty pop), and the worker calls it every iteration of its main
loop — including the idle one, which fires every `delivery.xread_block_ms`
(seeded **5000 ms**). That is:

```
86,400,000 ms/day / 5,000 ms/tick = 17,280 ticks/day
17,280 ZPOPMIN calls/day, purely from being left running — before one alert fires
```

## Why that number is the actual finding

17,280 is **already above** the entire 16,600/day monthly-derived ceiling, and
nearly **1.3×** the Part 28 80% guard threshold (13,280) — from idle polling
alone, with zero alerts dispatched. A worker left running continuously for a
full day would exhaust the Upstash free tier's command budget on background
polling before doing any real work. This is not a demo-day risk in the "we
might run 53 alerts" sense Part 1.4 modelled — it is a **left-the-terminal-open**
risk, and given that `python run.py worker-cloud` is meant to be kept open for
the whole rehearsal/demo window (§6.14), it is the realistic failure mode.

## The fix — a config value, not a redesign

`delivery.xread_block_ms` is already an `app_config` row, not a literal in
code (Rule 1), so tuning it is a threshold change, not a rewrite. Raised from
**5,000 ms to 15,000 ms** — a 3× reduction in idle-tick frequency, applied via
`python run.py seed-config`:

| | Before | After |
|---|---|---|
| Idle ticks/day | 17,280 | **5,760** |
| Idle `ZPOPMIN` calls/day | 17,280 | **5,760** |
| Retry pickup latency (worst case) | 5 s | 15 s |

15 s of added worst-case retry latency is immaterial against the policy's own
`wait_before_next_s` values (45–120 s per step) — the schedule was never
sub-15-second precision in the first place.

## Revised worst case, with real rates and the fix applied

For a demo day with the worker running the full ~4-hour rehearsal-plus-live
window (14,400 s) and, generously, **10 real dispatch runs**:

| Source | Commands |
|---|---|
| Idle ticks (`14,400 s / 15 s`) | 960 × 1 ZPOPMIN = **960** |
| 10 dispatch runs × (310 baseline + 1.5 B3 average) | **3,115** |
| **Total** | **≈ 4,075** |

**4,075 / 16,600 ≈ 24.5% of the daily ceiling — 4.08× headroom**, short of the
stated **5×** target but not dangerously so, and computed from a genuinely
generous 4-hour continuous-run assumption. Running the worker only for the
actual demo slot (closer to 1–2 hours, per `docs/demo-device.md`'s script)
brings idle ticks down to 240–480 and total commands to ≈2,600–2,850, which
clears 5× headroom (16,600 / 5 = 3,320) with margin.

**Operational rule, not just an arithmetic footnote:** stop
`worker-cloud` between rehearsals rather than leaving it running across a full
day. The command cost is dominated by idle time, not alert volume, so the
single highest-leverage thing anyone can do for this budget is not open a
terminal and forget about it.

## What this does not cover

This re-derivation only prices `services/delivery/worker.py`'s own loop. It
does not re-derive the WebSocket ops-console cost (Part 13's 50-client target)
or the ingestion poller's cadence, neither of which changed today. A full
demo-day counter check per Part 28's runbook — reading Upstash's own usage
dashboard at T-30 min — is still the authoritative measurement and remains
unrun; this document is the *design* re-derivation the roadmap asked for, not
a substitute for checking the real dashboard before going live.
