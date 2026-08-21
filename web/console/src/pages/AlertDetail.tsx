import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Send } from "lucide-react";
import {
  ApiError,
  endpoints,
  type AlertDetail as AlertDetailT,
  type AssuranceResponse,
  type PublicConfig,
  type ValidateResponse,
} from "../lib/api";
import { SeverityBadge } from "../components/SeverityBadge";
import { QualityGate } from "../components/QualityGate";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { AssuranceLadder } from "../components/AssuranceLadder";
import { Kpi } from "../components/Kpi";

function cfgInt(cfg: PublicConfig | null, key: string): number | null {
  const value = cfg?.[key];
  return typeof value === "number" ? value : null;
}

export function AlertDetail({
  id,
  onBack,
  onIncident,
  onOpen,
}: {
  id: number;
  onBack: () => void;
  onIncident?: (incidentId: number) => void;
  onOpen?: (alertId: number) => void;
}) {
  const [alert, setAlert] = useState<AlertDetailT | null>(null);
  const [gate, setGate] = useState<ValidateResponse | null>(null);
  const [assurance, setAssurance] = useState<AssuranceResponse | null>(null);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [approvals, setApprovals] = useState<{ have: number; need: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "danger"; text: string } | null>(null);
  const [selfApproved, setSelfApproved] = useState(false);
  const [changeReason, setChangeReason] = useState("");
  const [nextSeverity, setNextSeverity] = useState("");

  const refresh = useCallback(async () => {
    const [a, s, publicCfg] = await Promise.all([
      endpoints.alert(id),
      endpoints.assurance(id),
      endpoints.publicConfig(),
    ]);
    setAlert(a);
    setAssurance(s);
    setCfg(publicCfg);
    setApprovals({ have: a.approval_have, need: a.approval_need });
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function runGate() {
    setBusy("gate");
    try {
      setGate(await endpoints.validate(id));
      setNotice(null);
    } catch {
      setNotice({ tone: "danger", text: "Could not run the quality gate." });
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    setBusy("approve");
    try {
      const res = await endpoints.approve(id);
      setApprovals({ have: res.have, need: res.need });
      setSelfApproved(true);
      setNotice(null);
    } catch {
      setNotice({ tone: "danger", text: "Could not record the approval." });
    } finally {
      setBusy(null);
    }
  }

  async function dispatch() {
    setBusy("dispatch");
    setNotice(null);
    try {
      const res = await endpoints.dispatch(id);
      setNotice({
        tone: "ok",
        text: `Dispatched to ${res.recipient_count.toLocaleString()} recipients.`,
      });
      await refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.detail as Record<string, unknown> | undefined;
        if (err.code === "quality_gate") {
          const failures = (d?.failures as { rule_id: string; message: string }[]) ?? [];
          setGate({
            alert_id: id,
            blocked: true,
            results: failures.map((f) => ({
              rule_id: f.rule_id,
              status: "fail" as const,
              message: f.message,
            })),
          });
          setNotice({ tone: "danger", text: "Dispatch blocked by the quality gate." });
        } else if (err.code === "approval_quorum" || err.code === "approval_required") {
          setApprovals({ have: Number(d?.have ?? 0), need: Number(d?.need ?? 0) });
          setNotice({ tone: "danger", text: "Dispatch blocked — authorization incomplete." });
        } else if (err.code === "unit_scope") {
          setNotice({ tone: "danger", text: "This alert is outside your district." });
        } else {
          setNotice({ tone: "danger", text: `Dispatch failed (${err.code}).` });
        }
      }
    } finally {
      setBusy(null);
    }
  }

  async function escalate() {
    if (!changeReason.trim()) {
      setNotice({ tone: "danger", text: "A change reason is required to open a new version." });
      return;
    }
    setBusy("version");
    setNotice(null);
    try {
      const created = await endpoints.newVersion(id, {
        change_reason: changeReason.trim(),
        severity: nextSeverity || undefined,
      });
      if (onOpen) onOpen(created.alert_id);
    } catch {
      setNotice({ tone: "danger", text: "Could not create a new version." });
    } finally {
      setBusy(null);
    }
  }

  async function downloadPdf() {
    setBusy("pdf");
    try {
      const blob = await endpoints.reportPdf(id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `setu-alert-${id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setNotice({ tone: "danger", text: "Could not generate the audit PDF." });
    } finally {
      setBusy(null);
    }
  }

  if (!alert) return <div className="screen"><p className="muted">Loading…</p></div>;

  const gateBlocks = gate?.blocked ?? false;
  const have = approvals?.have ?? alert.approval_have;
  const need = approvals?.need ?? alert.approval_need;
  const approvalsShort = have < need;
  const dispatchDisabled = busy !== null || gateBlocks || approvalsShort;

  const deliveries = assurance?.deliveries ?? [];
  const reachedFloor = cfgInt(cfg, "reachability.reached_tier_floor");
  const ackedFloor = cfgInt(cfg, "reachability.acknowledged_tier_floor");
  const extraLadders = cfgInt(cfg, "ui.ladder_extra_sample") ?? 0;
  const reached = reachedFloor == null ? 0 : deliveries.filter((d) => d.assurance_level >= reachedFloor).length;
  const acked = ackedFloor == null ? 0 : deliveries.filter((d) => d.assurance_level >= ackedFloor).length;

  const sample = (() => {
    const seen = new Set<string>();
    const perChannel: typeof deliveries = [];
    for (const d of deliveries) {
      if (!seen.has(d.channel_code)) {
        seen.add(d.channel_code);
        perChannel.push(d);
      }
    }
    const rest = deliveries.filter((d) => !perChannel.includes(d)).slice(0, extraLadders);
    return [...perChannel, ...rest];
  })();

  return (
    <div className="screen">
      <header className="screen__head">
        <button className="btn btn--ghost" onClick={onBack}>
          <ArrowLeft size={14} aria-hidden /> Back
        </button>
        <div>
          <p className="screen__kicker">Alert</p>
          <h2>
            <span className="mono muted">#{alert.id}</span> {alert.headline}
          </h2>
        </div>
        <SeverityBadge severity={alert.severity} />
        <span className={`status status--${alert.lifecycle_status}`}>
          {alert.lifecycle_status}
        </span>
        {alert.incident_id && onIncident && (
          <button className="btn btn--ghost" onClick={() => onIncident(alert.incident_id!)}>
            Incident
          </button>
        )}
        <button className="btn btn--ghost" onClick={() => void downloadPdf()} disabled={busy !== null}>
          Audit PDF
        </button>
      </header>

      <p className="alert__body">{alert.body}</p>

      <section className="kpis" aria-label="Delivery summary">
        <Kpi label="Targeted" value={alert.target_count} />
        <Kpi label="Deliveries" value={deliveries.length} />
        {reachedFloor != null && (
          <Kpi
            label="Device delivered"
            value={reached}
            tone="info"
            note={`tier ${reachedFloor}+ — provider acceptance alone does not count`}
          />
        )}
        {ackedFloor != null && (
          <Kpi label="Acknowledged" value={acked} tone={acked ? "ok" : undefined} />
        )}
      </section>

      <div className="detail__cols">
        <div className="detail__col">
          <div className="panel detail__box">
            <h3>Pre-dispatch</h3>
            {gate ? (
              <QualityGate results={gate.results} blocked={gate.blocked} />
            ) : (
              <p className="muted">
                Quality gate has not been run for this alert yet.
              </p>
            )}
            <button
              className="btn btn--ghost"
              onClick={() => void runGate()}
              disabled={busy === "gate"}
            >
              {busy === "gate" ? "Running…" : "Run quality gate"}
            </button>
          </div>

          <div className="panel detail__box">
            <ApprovalPanel
              have={have}
              need={need}
              authoritative={alert.is_authoritative}
              onApprove={alert.is_authoritative ? undefined : () => void approve()}
              approving={busy === "approve"}
              selfAlreadyApproved={selfApproved}
            />
          </div>

          <div className="panel detail__box detail__dispatch">
            <button
              className="btn btn--danger"
              onClick={() => void dispatch()}
              disabled={dispatchDisabled}
            >
              <Send size={14} aria-hidden />
              {busy === "dispatch" ? "Dispatching…" : "Dispatch alert"}
            </button>
            {gateBlocks && (
              <p className="danger detail__why">
                Blocked: the quality gate has failing checks above.
              </p>
            )}
            {approvalsShort && (
              <p className="danger detail__why">
                Blocked: {have} of {need} approvals recorded.
                The second approval must come from a different officer.
              </p>
            )}
            {notice && (
              <p className={notice.tone === "ok" ? "ok detail__why" : "danger detail__why"} role="status">
                {notice.text}
              </p>
            )}
          </div>

          <div className="panel detail__box">
            <h3>New version</h3>
            <p className="muted">Escalating severity drafts vN+1. Change reason is required.</p>
            <label className="field">
              <span>Change reason</span>
              <input value={changeReason} onChange={(e) => setChangeReason(e.target.value)} />
            </label>
            <label className="field">
              <span>Severity</span>
              <select value={nextSeverity} onChange={(e) => setNextSeverity(e.target.value)}>
                <option value="">Keep current</option>
                <option value="minor">minor</option>
                <option value="moderate">moderate</option>
                <option value="severe">severe</option>
                <option value="extreme">extreme</option>
              </select>
            </label>
            <button
              className="btn"
              type="button"
              disabled={busy !== null || !changeReason.trim()}
              onClick={() => void escalate()}
            >
              {busy === "version" ? "Creating…" : "Create new version"}
            </button>
          </div>
        </div>

        <div className="detail__col">
          <div className="panel detail__box">
            <h3>Delivery assurance</h3>
            {deliveries.length === 0 && (
              <p className="muted">
                No deliveries yet. The ladder fills in as evidence arrives.
              </p>
            )}
            <div className="ladders">
              {sample.map((d) => (
                <AssuranceLadder key={d.delivery_id} delivery={d} />
              ))}
            </div>
            {deliveries.length > sample.length && (
              <p className="muted">
                Showing {sample.length} of {deliveries.length.toLocaleString()}{" "}
                deliveries — one per channel first, then most recent.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
