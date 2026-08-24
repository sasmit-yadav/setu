import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Send, Siren } from "lucide-react";
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
import { shortDateTime } from "../lib/time";
import { SeverityBadge } from "../components/SeverityBadge";
import { QualityGate } from "../components/QualityGate";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { AssuranceLadder } from "../components/AssuranceLadder";
import { Kpi } from "../components/Kpi";
import { ReplyInbox } from "../components/ReplyInbox";
import { useOpsSocket } from "../lib/useOpsSocket";

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
  // "warn" is for an action that was correctly refused rather than failed:
  // pressing Sound the siren twice is not an error, and colouring it red
  // would tell the officer something went wrong when nothing did.
  const [notice, setNotice] = useState<{
    tone: "ok" | "warn" | "danger";
    text: string;
  } | null>(null);
  const [selfApproved, setSelfApproved] = useState(false);
  const [changeReason, setChangeReason] = useState("");
  const [nextSeverity, setNextSeverity] = useState("");

  const refresh = useCallback(async () => {
    const [a, s, publicCfg, nextReplies, nextGate] = await Promise.all([
      endpoints.alert(id),
      endpoints.assurance(id),
      endpoints.publicConfig(),
      endpoints.alertResponses(id).catch(() => [] as CitizenReply[]),
      endpoints.validate(id).catch(() => null),
    ]);
    setAlert(a);
    setAssurance(s);
    setCfg(publicCfg);
    setReplies(nextReplies);
    setApprovals({ have: a.approval_have, need: a.approval_need });
    if (nextGate) setGate(nextGate);
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);
  useOpsSocket(() => void refresh());

  const waitingTranslation = Boolean(
    gate?.results.some((r) => r.rule_id === "translation_exists" && r.status === "fail"),
  );
  useEffect(() => {
    if (!waitingTranslation) return;
    let n = 0;
    const timer = window.setInterval(() => {
      n += 1;
      if (n > 45) {
        window.clearInterval(timer);
        return;
      }
      void endpoints
        .validate(id)
        .then((next) => setGate(next))
        .catch(() => {
          /* laptop translator may still be loading */
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [id, waitingTranslation]);

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

  async function soundSiren() {
    // Two steps on purpose. Every other button here sends to phones; this one
    // wakes a village whether or not anyone in it owns a phone, so it asks once.
    if (!window.confirm(t("siren.confirm"))) return;
    setBusy("siren");
    setNotice(null);
    try {
      const res = await endpoints.soundSiren(id);
      setNotice({
        tone: res.already_sounded ? "warn" : "ok",
        text: !res.already_sounded
          ? t("siren.done", { n: res.sirens })
          : res.last_sounded_at
            ? t("siren.already", {
                seconds: res.cooldown_seconds ?? 0,
                when: shortDateTime(res.last_sounded_at),
              })
            // No timestamp means one is queued rather than recently sounded.
            : t("siren.inFlight"),
      });
      await refresh();
    } catch (err) {
      const code = err instanceof ApiError ? err.code : undefined;
      setNotice({
        tone: "danger",
        text:
          code === "no_siren_registered_in_area"
            ? t("siren.none")
            : code === "alert_not_active"
              ? t("siren.notLive")
              : t("siren.fail"),
      });
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

      {alert.lifecycle_status === "active" || replies.length > 0 ? (
        <ReplyInbox rows={replies} cfg={cfg} />
      ) : null}

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
            {alert.lifecycle_status === "active" && (
              <button
                className="btn btn--ghost siren-btn"
                onClick={() => void soundSiren()}
                disabled={busy !== null}
                title={t("siren.hint")}
              >
                <Siren size={14} aria-hidden />
                {busy === "siren" ? t("siren.sounding") : t("siren.button")}
              </button>
            )}
            {alert.lifecycle_status === "active" && (
              <p className="muted detail__why">{t("siren.hint")}</p>
            )}
            {gateBlocks && (
              <p className="danger detail__why">{t("gate.blockedDispatch")}</p>
            )}
            {waitingTranslation && (
              <p className="muted detail__why">{t("compose.waitingTranslation")}</p>
            )}
            {approvalsShort && (
              <p className="danger detail__why">
                {t(need > 1 ? "approval.shortNeedOther" : "approval.short", { have, need })}
              </p>
            )}
            {notice && (
              <p
                className={
                  notice.tone === "ok"
                    ? "ok detail__why"
                    : notice.tone === "warn"
                      ? "warn detail__why"
                      : "danger detail__why"
                }
                role="status"
              >
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
