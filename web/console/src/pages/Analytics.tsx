import { useEffect, useState } from "react";
import { endpoints, type LeadTime, type OpsSummary } from "../lib/api";
import { Kpi } from "../components/Kpi";

export function Analytics() {
  const [lead, setLead] = useState<LeadTime | null>(null);
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [l, s] = await Promise.all([endpoints.leadTime(), endpoints.opsSummary()]);
        setLead(l);
        setSummary(s);
      } catch {
        setError("Could not load analytics.");
      }
    })();
  }, []);

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Measurement</p>
          <h2>Analytics</h2>
        </div>
      </header>
      {error && <p className="danger" role="alert">{error}</p>}
      {summary && (
        <section className="kpis" aria-label="Active-alert delivery">
          <Kpi label="Targeted" value={summary.targeted} />
          <Kpi label="Delivered" value={summary.delivered} tone="info" note={summary.delivered_note} />
          <Kpi
            label="Acknowledged"
            value={summary.acknowledged}
            tone={summary.acknowledged ? "ok" : undefined}
            note={summary.acknowledged_note}
          />
          <Kpi
            label="At-risk"
            value={summary.at_risk}
            tone={summary.at_risk ? "danger" : "ok"}
            note={summary.at_risk_note}
          />
        </section>
      )}
      {lead && (
        <section className="panel detail__box" aria-label="Warning lead time">
          <h3>Warning lead time</h3>
          <p className="mono">
            p10 {lead.p10 ?? "n/a"} · p50 {lead.p50 ?? "n/a"} · p90 {lead.p90 ?? "n/a"} minutes
          </p>
          <p className="muted">
            Coverage {lead.coverage_pct}% ({lead.alerts_with_onset}/{lead.alerts_total}). {lead.exclusion_reason}
          </p>
        </section>
      )}
    </div>
  );
}
