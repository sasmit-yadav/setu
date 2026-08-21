import { useState } from "react";
import { ApiError, endpoints, type EnrollmentImport } from "../lib/api";

export function Enrollment() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<EnrollmentImport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "commit" | null>(null);

  async function run(dryRun: boolean) {
    if (!file) return;
    setBusy(dryRun ? "preview" : "commit");
    setError(null);
    try {
      const result = await endpoints.importRecipients(
        file,
        dryRun,
        dryRun ? undefined : preview?.preview_token ?? undefined,
      );
      setPreview(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.code === "dry_run_required" ? "Run the dry-run preview first." : err.message);
      } else {
        setError("Import failed.");
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Enrollment</p>
          <h2>CSV import</h2>
        </div>
      </header>
      <section className="panel detail__box">
        <p className="muted">
          A live import is blocked until a matching dry-run preview exists for the same file.
        </p>
        <label className="field">
          <span>CSV file</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setPreview(null);
            }}
          />
        </label>
        <div className="detail__dispatch">
          <button className="btn" disabled={!file || busy !== null} onClick={() => void run(true)}>
            {busy === "preview" ? "Previewing…" : "Dry-run preview"}
          </button>
          <button
            className="btn btn--danger"
            disabled={!file || !preview?.dry_run || !preview.preview_token || busy !== null}
            onClick={() => void run(false)}
          >
            {busy === "commit" ? "Importing…" : "Commit import"}
          </button>
        </div>
        {error && <p className="danger" role="alert">{error}</p>}
        {preview && (
          <p className="mono">
            rows {preview.total_rows} · inserted {preview.inserted} · skipped {preview.skipped} · rejected {preview.rejected}
            {preview.dry_run ? " · dry-run" : " · committed"}
          </p>
        )}
      </section>
    </div>
  );
}
