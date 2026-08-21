import { useEffect, useState } from "react";
import { endpoints, type LeadTime, type OpsSummary } from "../lib/api";
import { useT } from "../lib/i18n";
import { Kpi } from "../components/Kpi";

export function Analytics() {
  const { t } = useT();
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
        setError(t("analytics.loadError"));
      }
    })();
  }, [t]);

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("analytics.kicker")}</p>
          <h2>{t("analytics.title")}</h2>
        </div>
      </header>
      {error && <p className="danger" role="alert">{error}</p>}
      {summary && (
        <section className="kpis" aria-label={t("live.title")}>
          <Kpi label={t("live.kpiTargeted")} value={summary.targeted} />
          <Kpi label={t("live.kpiDelivered")} value={summary.delivered} tone="info" note={summary.delivered_note} />
          <Kpi
            label={t("live.kpiAcked")}
            value={summary.acknowledged}
            tone={summary.acknowledged ? "ok" : undefined}
            note={summary.acknowledged_note}
          />
          <Kpi
            label={t("live.kpiRisk")}
            value={summary.at_risk}
            tone={summary.at_risk ? "danger" : "ok"}
            note={summary.at_risk_note}
          />
        </section>
      )}
      {lead && (
        <section className="panel detail__box" aria-label={t("analytics.lead")}>
          <h3>{t("analytics.lead")}</h3>
          <p>
            {t("analytics.leadLine", {
              p10: lead.p10 ?? t("analytics.na"),
              p50: lead.p50 ?? t("analytics.na"),
              p90: lead.p90 ?? t("analytics.na"),
            })}
          </p>
          <p className="muted">
            {t("analytics.coverage", {
              pct: lead.coverage_pct,
              have: lead.alerts_with_onset,
              total: lead.alerts_total,
              reason: lead.exclusion_reason,
            })}
          </p>
        </section>
      )}
    </div>
  );
}
