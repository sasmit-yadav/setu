import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  endpoints,
  type AlertSummary,
  type MapPayload,
  type PreviewResponse,
  type PublicConfig,
  type ValidateResponse,
} from "../lib/api";
import { useT } from "../lib/i18n";
import { LiveMap } from "../components/LiveMap";
import { QualityGate } from "../components/QualityGate";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { SeverityBadge } from "../components/SeverityBadge";
import { ProvenanceChip } from "../components/ProvenanceChip";

export function Composer({
  onOpen,
  onBack,
}: {
  onOpen: (id: number) => void;
  onBack: () => void;
}) {
  const { t } = useT();
  const [map, setMap] = useState<MapPayload | null>(null);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [polygon, setPolygon] = useState<Record<string, unknown> | null>(null);
  const [unitId, setUnitId] = useState<number | null>(null);
  const [unitName, setUnitName] = useState<string | null>(null);
  const [severity, setSeverity] = useState("");
  const [headline, setHeadline] = useState("");
  const [body, setBody] = useState("");
  const [expires, setExpires] = useState("");
  const [onset, setOnset] = useState("");
  const [alertId, setAlertId] = useState<number | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [gate, setGate] = useState<ValidateResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<{ have: number; need: number } | null>(null);
  const [incoming, setIncoming] = useState<AlertSummary[]>([]);
  const [ownRecent, setOwnRecent] = useState<AlertSummary[]>([]);

  useEffect(() => {
    void (async () => {
      const [nextMap, nextCfg, usgsDrafts, gdacsDrafts, nextAlerts] = await Promise.all([
        endpoints.map(),
        endpoints.publicConfig(),
        endpoints.alerts({ source_id: "usgs", lifecycle_status: "draft", limit: 20 }),
        endpoints.alerts({ source_id: "gdacs", lifecycle_status: "draft", limit: 20 }),
        endpoints.alerts({ limit: 8 }),
      ]);
      setMap(nextMap);
      setCfg(nextCfg);
      setIncoming(
        [...usgsDrafts, ...gdacsDrafts].filter(
          (row) => row.source_id === "usgs" || row.source_id === "gdacs",
        ),
      );
      setOwnRecent(nextAlerts.filter((row) => row.source_id === "manual").slice(0, 6));
    })();
  }, []);

  const onPolygon = useCallback((geojson: Record<string, unknown>) => {
    setPolygon(geojson);
  }, []);

  const onUnit = useCallback((id: number) => {
    setUnitId(id);
    const name = map?.units.features.find((f) => Number(f.properties?.unit_id) === id)
      ?.properties?.name;
    setUnitName(typeof name === "string" ? name : `#${id}`);
  }, [map]);

  function failText(err: unknown, fallback: string): string {
    if (err instanceof ApiError) {
      const d = err.detail;
      if (typeof d === "string") return d;
      if (d && typeof d === "object") {
        const rec = d as Record<string, unknown>;
        if (typeof rec.message === "string") return rec.message;
        if (typeof rec.error === "string") return rec.error;
      }
      return err.message;
    }
    return err instanceof Error ? err.message : fallback;
  }

  async function createDraft() {
    setBusy("create");
    setError(null);
    let savedId: number | null = null;
    try {
      const created = await endpoints.createAlert({
        severity,
        headline,
        body,
        lang: "en",
        ...(unitId != null ? { unit_ids: [unitId] } : { geojson: polygon }),
        expires_at: expires ? new Date(expires).toISOString() : null,
        estimated_onset_at: onset ? new Date(onset).toISOString() : null,
      });
      savedId = created.alert_id;
      setAlertId(created.alert_id);
      const [nextPreview, nextGate, detail] = await Promise.all([
        endpoints.preview(created.alert_id),
        endpoints.validate(created.alert_id),
        endpoints.alert(created.alert_id),
      ]);
      setPreview(nextPreview);
      setGate(nextGate);
      setApprovals({ have: detail.approval_have, need: detail.approval_need });
    } catch (err) {
      setError(
        savedId
          ? t("compose.savedOpen", { id: savedId })
          : failText(err, t("compose.createError")),
      );
    } finally {
      setBusy(null);
    }
  }

  async function saveExpiry() {
    if (!alertId) return;
    setBusy("patch");
    try {
      await endpoints.patchAlert(alertId, {
        expires_at: expires ? new Date(expires).toISOString() : null,
      });
      setPreview(await endpoints.preview(alertId));
      setGate(await endpoints.validate(alertId));
    } catch {
      setError(t("compose.patchError"));
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    if (!alertId) return;
    setBusy("approve");
    try {
      setApprovals(await endpoints.approve(alertId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("approval.fail"));
    } finally {
      setBusy(null);
    }
  }

  async function dispatch() {
    if (!alertId) return;
    setBusy("dispatch");
    try {
      await endpoints.dispatch(alertId);
      onOpen(alertId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("alert.sendFail", { code: "blocked" }));
      if (alertId) setGate(await endpoints.validate(alertId));
    } finally {
      setBusy(null);
    }
  }

  const blocked = Boolean(gate?.blocked);

  return (
    <div className="screen screen--wide">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("compose.kicker")}</p>
          <h2>{t("compose.title")}</h2>
        </div>
        <button className="btn btn--ghost" onClick={onBack} aria-label={t("compose.back")}>
          {t("compose.back")}
        </button>
      </header>
      <p className="lede">{t("compose.lede")}</p>
      <section className="panel composer__intel" aria-label={t("compose.incoming")}>
        <p className="screen__kicker">{t("compose.incoming")}</p>
        <h3>{t("compose.incoming")}</h3>
        {incoming.length === 0 ? (
          <p className="muted">{t("compose.incomingEmpty")}</p>
        ) : (
          <ul className="composer__sources">
            {incoming.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className="composer__source"
                  onClick={() => onOpen(row.id)}
                >
                  <span className="muted">{row.source_id}</span>
                  <SeverityBadge severity={row.severity} />
                  <span className="composer__source-headline">{row.headline}</span>
                  {row.is_authoritative ? <ProvenanceChip kind="authoritative" /> : null}
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => onOpen(row.id)}>
                  {t("compose.open")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      {ownRecent.length > 0 && (
        <section className="panel composer__intel" aria-label={t("compose.incomingOwn")}>
          <p className="screen__kicker">{t("compose.incomingOwn")}</p>
          <h3>{t("compose.incomingOwn")}</h3>
          <ul className="composer__sources">
            {ownRecent.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className="composer__source"
                  onClick={() => onOpen(row.id)}
                >
                  <span className="muted">{row.source_id}</span>
                  <SeverityBadge severity={row.severity} />
                  <span className="composer__source-headline">{row.headline}</span>
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => onOpen(row.id)}>
                  {t("compose.open")}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {error && <p className="danger" role="alert" aria-live="polite">{error}</p>}
      <div className="composer">
        <div className="live-map-wrap">
          <LiveMap payload={map} cfg={cfg} draw onPolygon={onPolygon} onUnit={onUnit} />
        </div>
        <form
          className="panel detail__box composer__form briefing"
          aria-label={t("compose.title")}
          onSubmit={(e) => {
            e.preventDefault();
            void createDraft();
          }}
        >
          <label className="field">
            <span>{t("compose.severity")}</span>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} required>
              <option value="" disabled>
                {t("compose.pickSeverity")}
              </option>
              <option value="minor">{t("sev.minor")}</option>
              <option value="moderate">{t("sev.moderate")}</option>
              <option value="severe">{t("sev.severe")}</option>
              <option value="extreme">{t("sev.extreme")}</option>
            </select>
          </label>
          <label className="field">
            <span>{t("compose.headline")}</span>
            <input value={headline} onChange={(e) => setHeadline(e.target.value)} required />
          </label>
          <label className="field">
            <span>{t("compose.body")}</span>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} required rows={4} />
          </label>
          <label className="field">
            <span>{t("compose.expires")}</span>
            <input type="datetime-local" value={expires} onChange={(e) => setExpires(e.target.value)} />
          </label>
          <label className="field">
            <span>{t("compose.onset")}</span>
            <input type="datetime-local" value={onset} onChange={(e) => setOnset(e.target.value)} />
          </label>
          {unitName ? (
            <p className="muted">{t("compose.villagePicked", { name: unitName })}</p>
          ) : (
            <p className="muted">{t("compose.pickVillage")}</p>
          )}
          <button
            className="btn btn--primary"
            type="submit"
            disabled={busy !== null || !severity || !headline || !body || (unitId == null && !polygon)}
          >
            {busy === "create" ? t("compose.creating") : t("compose.create")}
          </button>
          {alertId && (
            <button className="btn" type="button" onClick={() => void saveExpiry()} disabled={busy !== null}>
              {t("compose.saveExpiry")}
            </button>
          )}
          {preview && (
            <>
              <p>
                {t("compose.previewLine", {
                  id: preview.alert_id,
                  people: preview.recipient_count,
                  units: preview.units.length,
                })}
              </p>
              {preview.recipient_count === 0 ? (
                <p className="danger" role="status">
                  {t("compose.noPeople")}
                </p>
              ) : null}
              <ul className="muted">
                {preview.units.slice(0, 8).map((row) => (
                  <li key={row.unit_id}>
                    {t("compose.peopleIn", { name: row.name, n: row.recipients })}
                  </li>
                ))}
              </ul>
            </>
          )}
          {gate && <QualityGate results={gate.results} blocked={gate.blocked} />}
          {alertId && (
            <ApprovalPanel
              have={approvals?.have ?? 0}
              need={approvals?.need ?? 0}
              onApprove={() => void approve()}
              approving={busy === "approve"}
            />
          )}
          <button
            className="btn btn--danger"
            type="button"
            disabled={!alertId || blocked || busy !== null}
            onClick={() => void dispatch()}
          >
            {busy === "dispatch" ? t("compose.sending") : t("compose.send")}
          </button>
          {blocked && gate && (
            <p className="danger detail__why">
              {t("compose.blocked", {
                rules: gate.results.filter((r) => r.status === "fail").map((r) => r.rule_id).join(", "),
              })}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
