import { useCallback, useEffect, useState } from "react";
import {
  endpoints,
  type AlertSummary,
  type MapPayload,
  type PreviewResponse,
  type PublicConfig,
  type ValidateResponse,
} from "../lib/api";
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
  const [map, setMap] = useState<MapPayload | null>(null);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [polygon, setPolygon] = useState<Record<string, unknown> | null>(null);
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

  useEffect(() => {
    void (async () => {
      const [nextMap, nextCfg, nextAlerts] = await Promise.all([
        endpoints.map(),
        endpoints.publicConfig(),
        endpoints.alerts(),
      ]);
      setMap(nextMap);
      setCfg(nextCfg);
      const active = nextAlerts.filter((row) => row.lifecycle_status === "active");
      setIncoming((active.length ? active : nextAlerts).slice(0, 8));
    })();
  }, []);

  const onPolygon = useCallback((geojson: Record<string, unknown>) => {
    setPolygon(geojson);
  }, []);

  async function createDraft() {
    setBusy("create");
    setError(null);
    try {
      const created = await endpoints.createAlert({
        severity,
        headline,
        body,
        lang: "en",
        geojson: polygon,
        expires_at: expires ? new Date(expires).toISOString() : null,
        estimated_onset_at: onset ? new Date(onset).toISOString() : null,
      });
      setAlertId(created.alert_id);
      const [nextPreview, nextGate, detail] = await Promise.all([
        endpoints.preview(created.alert_id),
        endpoints.validate(created.alert_id),
        endpoints.alert(created.alert_id),
      ]);
      setPreview(nextPreview);
      setGate(nextGate);
      setApprovals({ have: detail.approval_have, need: detail.approval_need });
    } catch {
      setError("Could not create the draft. Draw a closed polygon first.");
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
      setError("Could not update expiry.");
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
      setError(err instanceof Error ? err.message : "Approval failed.");
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
      setError(err instanceof Error ? err.message : "Dispatch blocked.");
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
          <p className="screen__kicker">Mission briefing</p>
          <h2>Compose alert</h2>
        </div>
        <button className="btn btn--ghost" onClick={onBack} aria-label="Back to live ops">Back</button>
      </header>
      <p className="muted">
        Incoming rows below are whatever the ingest table holds right now. Load one, then draw over the labelled village it names. Close the polygon with at least three points. Dispatch needs at least one enrolled resident inside that area.
      </p>
      <section className="panel composer__intel" aria-label="Incoming sources">
        <p className="screen__kicker">Incoming sources</p>
        <h3>Briefing</h3>
        {incoming.length === 0 ? (
          <p className="muted">No ingested alerts in this session. Draw only from a field report.</p>
        ) : (
          <ul className="composer__sources">
            {incoming.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className="composer__source"
                  onClick={() => {
                    setSeverity(String(row.severity));
                    setHeadline(row.headline);
                  }}
                >
                  <span className="mono muted">{row.source_id}</span>
                  <SeverityBadge severity={row.severity} />
                  <span className="composer__source-headline">{row.headline}</span>
                  {row.is_authoritative ? <ProvenanceChip kind="authoritative" /> : null}
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => onOpen(row.id)}>
                  Open
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      {error && <p className="danger" role="alert" aria-live="polite">{error}</p>}
      <div className="composer">
        <LiveMap payload={map} cfg={cfg} draw onPolygon={onPolygon} />
        <form
          className="panel detail__box composer__form briefing"
          aria-label="Compose alert"
          onSubmit={(e) => {
            e.preventDefault();
            void createDraft();
          }}
        >
          <label className="field">
            <span>Severity</span>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} required>
              <option value="" disabled>
                Select from an incoming source
              </option>
              <option value="minor">minor</option>
              <option value="moderate">moderate</option>
              <option value="severe">severe</option>
              <option value="extreme">extreme</option>
            </select>
          </label>
          <label className="field">
            <span>Headline</span>
            <input value={headline} onChange={(e) => setHeadline(e.target.value)} required />
          </label>
          <label className="field">
            <span>Body</span>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} required rows={4} />
          </label>
          <label className="field">
            <span>Expires at</span>
            <input type="datetime-local" value={expires} onChange={(e) => setExpires(e.target.value)} />
          </label>
          <label className="field">
            <span>Estimated onset</span>
            <input type="datetime-local" value={onset} onChange={(e) => setOnset(e.target.value)} />
          </label>
          <button className="btn btn--primary" type="submit" disabled={busy !== null || !severity || !headline || !body}>
            {busy === "create" ? "Creating…" : "Create draft"}
          </button>
          {alertId && (
            <button className="btn" type="button" onClick={() => void saveExpiry()} disabled={busy !== null}>
              Save expiry and re-validate
            </button>
          )}
          {preview && (
            <>
              <p className="mono">
                Alert #{preview.alert_id} · {preview.recipient_count} recipients · {preview.units.length} units
              </p>
              {preview.recipient_count === 0 ? (
                <p className="danger" role="status">
                  No enrolled residents inside this polygon. Draw over a labelled village, not empty sea or unnamed land.
                </p>
              ) : null}
              <ul className="muted">
                {preview.units.slice(0, 8).map((row) => (
                  <li key={row.unit_id}>
                    {row.name} · {row.recipients}
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
            {busy === "dispatch" ? "Dispatching…" : "Dispatch"}
          </button>
          {blocked && gate && (
            <p className="danger detail__why">
              Dispatch blocked — {gate.results.filter((r) => r.status === "fail").map((r) => r.rule_id).join(", ")}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
