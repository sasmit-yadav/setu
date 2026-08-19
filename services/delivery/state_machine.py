from __future__ import annotations

from typing import Any

import asyncpg

from services.audit.ledger import append_audit
from services.delivery.states import LEGAL, TIMESTAMP_COL, IllegalTransition, State


async def transition(
    conn: asyncpg.Connection,
    delivery_id: int,
    to: State,
    *,
    actor: str | None = None,
    **ctx: Any,
) -> None:
    row = await conn.fetchrow(
        "SELECT state, attempt, alert_id FROM delivery WHERE id = $1 FOR UPDATE",
        delivery_id,
    )
    if row is None:
        raise ValueError(f"delivery {delivery_id} not found")
    frm = State(row["state"])
    if to not in LEGAL[frm]:
        raise IllegalTransition(frm, to)
    ts_col = TIMESTAMP_COL[to]
    # delivery.failed_reason is a real column and must actually be written.
    # It was previously only ever recorded inside the audit payload, so every
    # failed delivery showed failed_reason = NULL while the ledger knew
    # exactly why. Rule 4 says every figure a user sees resolves to a stored
    # fact — "failed, reason unknown" on a console is that rule breaking,
    # even though the ledger held the answer all along.
    reason = ctx.get("reason")
    set_reason = to in (State.failed, State.expired) and reason is not None

    assignments = ["state = $2"]
    params: list[Any] = [delivery_id, to.value]
    if ts_col:
        assignments.append(f"{ts_col} = now()")
    if set_reason:
        params.append(str(reason))
        assignments.append(f"failed_reason = ${len(params)}")

    await conn.execute(
        f"UPDATE delivery SET {', '.join(assignments)} WHERE id = $1",
        *params,
    )
    payload = {"from": frm.value, "to": to.value, "attempt": row["attempt"], **ctx}
    await append_audit(
        conn,
        alert_id=row["alert_id"],
        delivery_id=delivery_id,
        event_type=f"delivery.{to.value}",
        payload=payload,
        actor=actor,
    )
