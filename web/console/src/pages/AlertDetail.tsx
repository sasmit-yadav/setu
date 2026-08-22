import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Send } from "lucide-react";
import {
  ApiError,
  endpoints,
  type AlertDetail as AlertDetailT,
  type AssuranceResponse,
  type CitizenReply,
  type PublicConfig,
  type ValidateResponse,
} from "../lib/api";
import { lookup, useT } from "../lib/i18n";
import { SeverityBadge } from "../components/SeverityBadge";
import { QualityGate } from "../components/QualityGate";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { AssuranceLadder } from "../components/AssuranceLadder";
import { Kpi } from "../components/Kpi";
import { useOpsSocket } from "../lib/useOpsSocket";
import { saidLabel, viaLabel } from "../lib/replies";

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
  const { t } = useT();
  const [alert, setAlert] = useState<AlertDetailT | null>(null);
  const [gate, setGate] = useState<ValidateResponse | null>(null);
  const [assurance, setAssurance] = useState<AssuranceResponse | null>(null);
  const [replies, setReplies] = useState<CitizenReply[]>([]);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [approvals, setApprovals] = useState<{ have: number; need: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "danger"; text: string } | null>(null);
  const [selfApproved, setSelfApproved] = useState(false);
  const [changeReason, setChangeReason] = useState("");
  const [nextSeverity, setNextSeverity] = useState("");

  const refresh = useCallback(async () => {
    const [a, s, publicCfg, nextReplies] = await Promise.all([
      endpoints.alert(id),
      endpoints.assurance(id),
      endpoints.publicConfig(),
      endpoints.alertResponses(id).catch(() => [] as CitizenReply[]),
    ]);
    setAlert(a);
    setAssurance(s);
    setCfg(publicCfg);
    setReplies(nextReplies);
    setApprovals({ have: a.approval_have, need: a.approval_need });
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);
  useOpsSocket(() => void refresh());

  async function runGate() {
    setBusy("gate");
    try {
      setGate(await endpoints.validate(id));
      setNotice(null);
    } catch {
      setNotice({ tone: "danger", text: t("gate.runError") });
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
      setNotice({ tone: "danger", text: t("approval.fail") });
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
        text: t("alert.sentOk", { n: res.recipient_count.toLocaleString() }),
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
          setNotice({ tone: "danger", text: t("gate.blockedDispatch") });
        } else if (err.code === "approval_quorum" || err.code === "approval_required") {
          setApprovals({ have: Number(d?.have ?? 0), need: Number(d?.need ?? 0) });
          setNotice({ tone: "danger", text: t("alert.authIncomplete") });
        } else if (err.code === "unit_scope") {
          setNotice({ tone: "danger", text: t("alert.outOfDistrict") });
        } else {
          setNotice({ tone: "danger", text: t("alert.sendFail", { code: err.code }) });
        }
      }
    } finally {
      setBusy(null);
    }
  }

  async function escalate() {
    if (!changeReason.trim()) {
      setNotice({ tone: "danger", text: t("alert.reasonNeeded") });
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
      setNotice({ tone: "danger", text: t("alert.versionFail") });
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
      setNotice({ tone: "danger", text: t("alert.pdfFail") });
    } finally {
      setBusy(null);
    }
  }

  if (!alert) return <div className="screen"><p className="muted">{t("alert.loading")}</p></div>;

  const gateBlocks = gate?.blocked ?? false;
  const have = approvals?.have ?? alert.approval_have;
  const need = approvals?.need ?? alert.approval_need;
  const approvalsShort = have < need;
  const dispatchDisabled = busy !== null || gateBlocks || approvalsShort;

  const deliveries = assurance?.deliveries ?? [];
  const reachedFloor = cfgInt(cfg, "reachability.reached_tier_floor");
  const ackedFloor = cfgInt(cfg, "reachability.acknowledged_tier_floor");
  const extraLadders = cfgInt(cfg, "ui.ladder_extra_sample") ?? 0;
  const reached =
    reachedFloor == null
      ? 0
      : deliveries.filter((d) => !d.simulated && d.assurance_level >= reachedFloor).length;
  const acked =
    ackedFloor == null
      ? 0
      : deliveries.filter(
          (d) =>
            (!d.simulated && d.assurance_level >= ackedFloor) ||
            d.rungs.some((r) => r.event_type === "citizen_response" && r.status === "recorded"),
        ).length;

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
          <ArrowLeft size={14} aria-hidden /> {t("alert.back")}
        </button>
        <div>
          <p className="screen__kicker">{t("alert.kicker")}</p>
          <h2>
            <span className="mono muted">#{alert.id}</span> {alert.headline}
          </h2>
        </div>
        <SeverityBadge severity={alert.severity} />
        <span className={`status status--${alert.lifecycle_status}`}>
          {lookup(t, "life", alert.lifecycle_status)}
        </span>
        {alert.incident_id && onIncident && (
          <button className="btn btn--ghost" onClick={() => onIncident(alert.incident_id!)}>
            {t("alert.emergency")}
          </button>
        )}
        <button className="btn btn--ghost" onClick={() => void downloadPdf()} disabled={busy !== null}>
          {t("alert.pdf")}
        </button>
      </header>

      <p className="alert__body">{alert.body}</p>

      <section className="kpis" aria-label={t("alert.proof")}>
        <Kpi label={t("alert.kpiTargeted")} value={alert.target_count} />
        <Kpi label={t("alert.kpiSends")} value={deliveries.length} />
        {reachedFloor != null && (
          <Kpi
            label={t("alert.kpiPhone")}
            value={reached}
            tone="info"
            note={t("alert.kpiPhoneNote")}
          />
        )}
        {ackedFloor != null && (
          <Kpi label={t("alert.kpiAcked")} value={acked} tone={acked ? "ok" : undefined} />
        )}
      </section>

      <div className="detail__cols">
        <div className="detail__col">
          <div className="panel detail__box">
            <h3>{t("alert.pre")}</h3>
            {gate ? (
              <QualityGate results={gate.results} blocked={gate.blocked} />
            ) : (
              <p className="muted">{t("gate.notRun")}</p>
            )}
            <button
              className="btn btn--ghost"
              onClick={() => void runGate()}
              disabled={busy === "gate"}
            >
              {busy === "gate" ? t("gate.running") : t("gate.run")}
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
              {busy === "dispatch" ? t("alert.sending") : t("alert.send")}
            </button>
            {gateBlocks && (
              <p className="danger detail__why">{t("gate.blockedDispatch")}</p>
            )}
            {approvalsShort && (
              <p className="danger detail__why">
                {t(need > 1 ? "approval.shortNeedOther" : "approval.short", { have, need })}
              </p>
            )}
            {notice && (
              <p className={notice.tone === "ok" ? "ok detail__why" : "danger detail__why"} role="status">
                {notice.text}
              </p>
            )}
          </div>

          <div className="panel detail__box">
            <h3>{t("alert.newVersion")}</h3>
            <p className="muted">{t("alert.newVersionHint")}</p>
            <label className="field">
              <span>{t("alert.reason")}</span>
              <input value={changeReason} onChange={(e) => setChangeReason(e.target.value)} />
            </label>
            <label className="field">
              <span>{t("compose.severity")}</span>
              <select value={nextSeverity} onChange={(e) => setNextSeverity(e.target.value)}>
                <option value="">{t("alert.keepSeverity")}</option>
                <option value="minor">{t("sev.minor")}</option>
                <option value="moderate">{t("sev.moderate")}</option>
                <option value="severe">{t("sev.severe")}</option>
                <option value="extreme">{t("sev.extreme")}</option>
              </select>
            </label>
            <button
              className="btn"
              type="button"
              disabled={busy !== null || !changeReason.trim()}
              onClick={() => void escalate()}
            >
              {busy === "version" ? t("alert.creatingVersion") : t("alert.createVersion")}
            </button>
          </div>
        </div>

        <div className="detail__col">
          <div className="panel detail__box">
            <h3>{t("alert.replies")}</h3>
            <p className="muted">{t("alert.repliesHint")}</p>
            {replies.length === 0 ? (
              <p className="muted">{t("alert.repliesEmpty")}</p>
            ) : (
              <div className="replies" role="list">
                {replies.map((row) => (
                  <div key={row.id} className="replies__row" role="listitem">
                    <span className="replies__via">{viaLabel(t, row.channel_code)}</span>
                    <span className="replies__said">
                      {saidLabel(cfg, row.response_type, row.free_text)}
                      <span className="replies__meta"> · {row.unit_name}</span>
                    </span>
                    <time className="mono muted" dateTime={row.received_at}>
                      {new Date(row.received_at).toLocaleTimeString()}
                    </time>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="panel detail__box">
            <h3>{t("alert.proof")}</h3>
            {deliveries.length === 0 && (
              <p className="muted">{t("alert.proofEmpty")}</p>
            )}
            <div className="ladders">
              {sample.map((d) => (
                <AssuranceLadder key={d.delivery_id} delivery={d} />
              ))}
            </div>
            {deliveries.length > sample.length && (
              <p className="muted">
                {t("alert.proofMore", {
                  shown: sample.length,
                  total: deliveries.length.toLocaleString(),
                })}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
