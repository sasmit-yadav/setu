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
    if ts_col:
        await conn.execute(
            f"UPDATE delivery SET state = $2, {ts_col} = now() WHERE id = $1",
            delivery_id,
            to.value,
        )
    else:
        await conn.execute(
            "UPDATE delivery SET state = $2 WHERE id = $1",
            delivery_id,
            to.value,
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
