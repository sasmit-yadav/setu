/** Alert Detail — where the governance layer becomes visible.
 *
 * This screen carries three of Part 0.5's four v3.0 visual beats at once: the
 * quality gate as a pre-flight checklist, the approval panel that is visibly
 * incomplete until a second human acts, and the assurance ladder with its
 * struck-through rungs.
 *
 * The composition rule from Part 0.5, applied literally: the reason a control
 * is blocked sits ADJACENT to that control. The dispatch button and the
 * sentence explaining why it is disabled are in the same box, always visible,
 * never a toast the officer can dismiss and forget.
 *
 * OPTIMISTIC UI IS BANNED HERE (Part 11.3). Nothing renders as approved,
 * dispatched or delivered until the server has confirmed it — "showing
 * 'acknowledged' before the server confirms would be a lie in exactly the
 * place lies are most dangerous". Every mutation below re-reads from the API
 * rather than patching local state.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Send } from "lucide-react";
import {
  ApiError,
  endpoints,
  type AlertDetail as AlertDetailT,
  type AssuranceResponse,
  type ValidateResponse,
} from "../lib/api";
import { SeverityBadge } from "../components/SeverityBadge";
import { QualityGate } from "../components/QualityGate";
import { ApprovalPanel } from "../components/ApprovalPanel";
import { AssuranceLadder } from "../components/AssuranceLadder";
import { Kpi } from "../components/Kpi";

const AUTHORITATIVE_SOURCES = new Set(["usgs", "gdacs"]);

export function AlertDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const [alert, setAlert] = useState<AlertDetailT | null>(null);
  const [gate, setGate] = useState<ValidateResponse | null>(null);
  const [assurance, setAssurance] = useState<AssuranceResponse | null>(null);
  const [approvals, setApprovals] = useState<{ have: number; need: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "danger"; text: string } | null>(null);
  const [selfApproved, setSelfApproved] = useState(false);

  const refresh = useCallback(async () => {
    const [a, s] = await Promise.all([endpoints.alert(id), endpoints.assurance(id)]);
    setAlert(a);
    setAssurance(s);
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const authoritative = alert ? AUTHORITATIVE_SOURCES.has(alert.source_id) : false;

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
      // The status-code contract (Part 10) is deliberately specific so the
      // officer is told WHICH gate stopped them, not a generic failure.
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
          setApprovals({ have: Number(d?.have ?? 0), need: Number(d?.need ?? 2) });
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

  if (!alert) return <div className="screen"><p className="muted">Loading…</p></div>;

  const gateBlocks = gate?.blocked ?? false;
  const approvalsShort = approvals ? approvals.have < approvals.need : false;
  const dispatchDisabled = busy !== null || gateBlocks || approvalsShort;

  const deliveries = assurance?.deliveries ?? [];
  const reached = deliveries.filter((d) => d.assurance_level >= 2).length;
  const acked = deliveries.filter((d) => d.assurance_level >= 4).length;

  // Progressive disclosure (Part 0.4.3): a 250-delivery alert must not render
  // 250 ladders. But the sample is chosen ONE PER CHANNEL FIRST, not "the
  // first 12 by id" — every channel proves a different SHAPE of evidence, and
  // a siren's three struck-through rungs are the most informative thing on
  // this screen. Ordering by id buried it behind 250 identical sim ladders.
  const sample = (() => {
    const seen = new Set<string>();
    const perChannel: typeof deliveries = [];
    for (const d of deliveries) {
      if (!seen.has(d.channel_code)) {
        seen.add(d.channel_code);
        perChannel.push(d);
      }
    }
    const rest = deliveries.filter((d) => !perChannel.includes(d)).slice(0, 8);
    return [...perChannel, ...rest];
  })();

  return (
    <div className="screen">
      <header className="screen__head">
        <button className="btn btn--ghost" onClick={onBack}>
          <ArrowLeft size={14} aria-hidden /> Back
        </button>
        <h2>
          <span className="mono muted">#{alert.id}</span> {alert.headline}
        </h2>
        <SeverityBadge severity={alert.severity} />
        <span className={`status status--${alert.lifecycle_status}`}>
          {alert.lifecycle_status}
        </span>
      </header>

      <p className="alert__body">{alert.body}</p>

      <section className="kpis" aria-label="Delivery summary">
        <Kpi label="Targeted" value={alert.target_count} />
        <Kpi label="Deliveries" value={deliveries.length} />
        <Kpi
          label="Device delivered"
          value={reached}
          tone="info"
          note="tier 2+ — provider acceptance alone does not count"
        />
        <Kpi label="Acknowledged" value={acked} tone={acked ? "ok" : undefined} />
      </section>

      <div className="detail__cols">
        <div className="detail__col">
          {/* ── governance ─────────────────────────────────────────── */}
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
              have={approvals?.have ?? 0}
              need={approvals?.need ?? (alert.severity === "severe" || alert.severity === "extreme" ? 2 : 1)}
              authoritative={authoritative}
              onApprove={authoritative ? undefined : () => void approve()}
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
            {/* The reason lives NEXT TO the button it blocks. Seatbelt, not
                nag — and never a dismissible banner. */}
            {gateBlocks && (
              <p className="danger detail__why">
                Blocked: the quality gate has failing checks above.
              </p>
            )}
            {approvalsShort && approvals && (
              <p className="danger detail__why">
                Blocked: {approvals.have} of {approvals.need} approvals recorded.
                The second approval must come from a different officer.
              </p>
            )}
            {notice && (
              <p className={notice.tone === "ok" ? "ok detail__why" : "danger detail__why"} role="status">
                {notice.text}
              </p>
            )}
          </div>
        </div>

        {/* ── evidence ─────────────────────────────────────────────── */}
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
              // Part 0.5's guardrail against silent truncation: say what is
              // being shown and what is being left out, rather than letting a
              // capped list read as the whole set.
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
