from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from typing import Any

import asyncpg

from services.api import config_repo
from services.api.settings import settings
from services.audit.ledger import append_audit
from services.enrollment.phone_hash import (
    PhoneNumberError,
    normalize_phone_e164,
    phone_hash,
)


class CsvImportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ImportRowResult:
    row_number: int
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class ImportSummary:
    total_rows: int
    inserted: int
    skipped: int
    rejected: int
    dry_run: bool
    rows: list[ImportRowResult]
    preview_token: str | None = None


def preview_token_for(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def _encrypt_phone(conn: asyncpg.Connection, phone_e164: str) -> bytes | None:
    if not settings.pgcrypto_sym_key:
        return None
    return await conn.fetchval(
        "SELECT pgp_sym_encrypt($1, $2)",
        phone_e164,
        settings.pgcrypto_sym_key,
    )


async def import_csv(
    conn: asyncpg.Connection,
    content: bytes,
    *,
    dry_run: bool,
    actor: str,
    preview_token: str | None = None,
) -> ImportSummary:
    require_dry_run = await config_repo.get_bool(conn, "enrollment.csv_require_dry_run")
    token = preview_token_for(content)
    if require_dry_run and not dry_run and preview_token != token:
        raise CsvImportError("dry_run_required", "Import requires a matching preview_token from dry_run")
    max_rows = await config_repo.get_int(conn, "enrollment.csv_max_rows")
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CsvImportError("invalid_csv", "CSV header row missing")
    required = {"phone", "unit_id"}
    if not required.issubset({h.strip().lower() for h in reader.fieldnames}):
        raise CsvImportError("invalid_csv", "CSV must include phone and unit_id columns")

    results: list[ImportRowResult] = []
    inserted = skipped = rejected = 0
    for row_number, row in enumerate(reader, start=2):
        if row_number - 1 > max_rows:
            raise CsvImportError("row_limit_exceeded", f"CSV exceeds enrollment.csv_max_rows ({max_rows})")
        normalized = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        phone_raw = normalized.get("phone", "")
        unit_raw = normalized.get("unit_id", "")
        preferred_lang = normalized.get("preferred_lang") or "en"
        push_token = normalized.get("push_token") or None
        if not phone_raw or not unit_raw:
            rejected += 1
            results.append(ImportRowResult(row_number, "rejected", "missing phone or unit_id"))
            continue
        try:
            unit_id = int(unit_raw)
        except ValueError:
            rejected += 1
            results.append(ImportRowResult(row_number, "rejected", "invalid unit_id"))
            continue
        unit_exists = await conn.fetchval("SELECT 1 FROM admin_unit WHERE id = $1", unit_id)
        if not unit_exists:
            rejected += 1
            results.append(ImportRowResult(row_number, "rejected", "unit_not_found"))
            continue
        try:
            phone_e164 = await normalize_phone_e164(conn, phone_raw)
        except PhoneNumberError as exc:
            rejected += 1
            results.append(ImportRowResult(row_number, "rejected", str(exc)))
            continue
        digest = phone_hash(phone_e164)
        existing = await conn.fetchval(
            "SELECT id FROM recipient WHERE phone_hash = $1",
            digest,
        )
        if existing:
            skipped += 1
            results.append(ImportRowResult(row_number, "skipped", "duplicate phone_hash"))
            continue
        if dry_run:
            inserted += 1
            results.append(ImportRowResult(row_number, "would_insert"))
            continue
        phone_enc = await _encrypt_phone(conn, phone_e164)
        recipient_id = await conn.fetchval(
            """
            INSERT INTO recipient (
                unit_id, kind, push_token, phone_enc, phone_hash,
                preferred_lang, consented_at, consent_source
            )
            VALUES ($1, 'citizen', $2, $3, $4, $5, now(), 'csv_import')
            RETURNING id
            """,
            unit_id,
            push_token,
            phone_enc,
            digest,
            preferred_lang,
        )
        inserted += 1
        results.append(ImportRowResult(row_number, "inserted", str(recipient_id)))

    summary = ImportSummary(
        total_rows=len(results),
        inserted=inserted,
        skipped=skipped,
        rejected=rejected,
        dry_run=dry_run,
        rows=results,
        preview_token=token if dry_run else None,
    )
    if not dry_run:
        await append_audit(
            conn,
            event_type="enrollment.csv_import",
            payload=_summary_payload(summary),
            actor=actor,
        )
    return summary


def _summary_payload(summary: ImportSummary) -> dict[str, Any]:
    return {
        "total_rows": summary.total_rows,
        "inserted": summary.inserted,
        "skipped": summary.skipped,
        "rejected": summary.rejected,
        "dry_run": summary.dry_run,
    }
