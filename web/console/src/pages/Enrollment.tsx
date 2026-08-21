import { useState } from "react";
import { ApiError, endpoints, type EnrollmentImport } from "../lib/api";
import { useT } from "../lib/i18n";

export function Enrollment() {
  const { t } = useT();
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
        setError(err.code === "dry_run_required" ? t("enroll.needPreview") : err.message);
      } else {
        setError(t("enroll.fail"));
      }
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("enroll.kicker")}</p>
          <h2>{t("enroll.title")}</h2>
        </div>
      </header>
      <section className="panel detail__box">
        <p className="lede">{t("enroll.lede")}</p>
        <label className="field">
          <span>{t("enroll.file")}</span>
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
            {busy === "preview" ? t("enroll.previewing") : t("enroll.preview")}
          </button>
          <button
            className="btn btn--danger"
            disabled={!file || !preview?.dry_run || !preview.preview_token || busy !== null}
            onClick={() => void run(false)}
          >
            {busy === "commit" ? t("enroll.committing") : t("enroll.commit")}
          </button>
        </div>
        {error && <p className="danger" role="alert">{error}</p>}
        {preview && (
          <p>
            {t("enroll.summary", {
              total: preview.total_rows,
              inserted: preview.inserted,
              skipped: preview.skipped,
              rejected: preview.rejected,
              mode: preview.dry_run ? t("enroll.dry") : t("enroll.saved"),
            })}
          </p>
        )}
      </section>
    </div>
  );
}
