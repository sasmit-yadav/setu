from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response

from services.api.auth import Principal
from services.api.deps import get_conn
from services.api.rbac import require_operational_read
from services.audit.timeline import incident_timeline

router = APIRouter(prefix="/api/v1", tags=["reports"])


def _pdf_bytes(title: str, lines: list[str]) -> bytes:
    content_cmds = ["BT", "/F1 11 Tf", "48 760 Td"]
    for index, line in enumerate([title, *lines]):
        escaped = (
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:180]
        )
        if index:
            content_cmds.append("0 -14 Td")
        content_cmds.append(f"({escaped}) Tj")
    content_cmds.append("ET")
    stream = "\n".join(content_cmds).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


@router.get("/alerts/{alert_id}/report.pdf")
async def alert_report_pdf(
    alert_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> Response:
    alert = await conn.fetchrow(
        """
        SELECT a.id, a.headline, a.severity, a.lifecycle_status, a.source_id,
               a.incident_id
        FROM alert a WHERE a.id = $1
        """,
        alert_id,
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="alert_not_found")
    target_count = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT r.id)
        FROM recipient r
        JOIN admin_unit u ON u.id = r.unit_id
        JOIN alert a ON a.id = $1
        WHERE ST_Intersects(u.geom, a.area)
          AND r.consented_at IS NOT NULL
          AND r.opted_out_at IS NULL
        """,
        alert_id,
    )
    events = []
    if alert["incident_id"]:
        events = await incident_timeline(conn, int(alert["incident_id"]))
    humans = await conn.fetch(
        """
        SELECT rc.households_claimed, rc.confirmed_at, rc.method
        FROM relay_confirmation rc
        JOIN delivery d ON d.id = rc.delivery_id
        WHERE d.alert_id = $1
        ORDER BY rc.confirmed_at
        """,
        alert_id,
    )
    lines = [
        f"Alert {alert['id']}  {alert['severity']}  {alert['lifecycle_status']}",
        f"Source {alert['source_id']}  targets {int(target_count or 0)}",
        alert["headline"],
        "",
        "HUMAN relay confirmations (distinct from digital delivery)",
    ]
    if not humans:
        lines.append("none")
    for row in humans:
        claimed = row["households_claimed"]
        lines.append(
            f"HUMAN  {row['confirmed_at']}  {row['method']}  households_claimed={claimed}"
        )
    lines.extend(["", "Timeline"])
    for event in events:
        lines.append(f"{event['occurred_at']}  {event['event_type']}  {event.get('actor') or ''}")
    body = _pdf_bytes("SETU audit report", lines)
    return Response(content=body, media_type="application/pdf")


@router.get("/alerts/{alert_id}/audit")
async def alert_audit(
    alert_id: int,
    conn: asyncpg.Connection = Depends(get_conn),
    _principal: Principal = Depends(require_operational_read),
) -> list[dict]:
    exists = await conn.fetchval("SELECT 1 FROM alert WHERE id = $1", alert_id)
    if not exists:
        raise HTTPException(status_code=404, detail="alert_not_found")
    rows = await conn.fetch(
        """
        SELECT id, event_type, payload, actor, occurred_at, prev_hash, hash
        FROM audit_event
        WHERE alert_id = $1
        ORDER BY id
        """,
        alert_id,
    )
    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "payload": row["payload"],
            "actor": row["actor"],
            "occurred_at": row["occurred_at"].isoformat(),
            "prev_hash": row["prev_hash"],
            "hash": row["hash"],
        }
        for row in rows
    ]
