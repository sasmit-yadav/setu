from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from services.api.deps import get_conn
from services.enrollment.csv_import import CsvImportError, import_csv

router = APIRouter(prefix="/api/v1/admin", tags=["enrollment"])


@router.post("/recipients/import")
async def import_recipients(
    dry_run: bool = Query(default=True),
    preview_token: str | None = Query(default=None),
    file: UploadFile = File(...),
    conn=Depends(get_conn),
) -> dict:
    content = await file.read()
    try:
        summary = await import_csv(
            conn,
            content,
            dry_run=dry_run,
            actor="officer",
            preview_token=preview_token,
        )
    except CsvImportError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.code, "message": exc.message}) from exc
    return {
        "total_rows": summary.total_rows,
        "inserted": summary.inserted,
        "skipped": summary.skipped,
        "rejected": summary.rejected,
        "dry_run": summary.dry_run,
        "preview_token": summary.preview_token,
        "rows": [
            {"row_number": row.row_number, "status": row.status, "reason": row.reason}
            for row in summary.rows
        ],
    }
