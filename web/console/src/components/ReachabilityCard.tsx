import { useEffect, useState } from "react";
import { ApiError, endpoints, type Reachability, type UnitRisk, type Vulnerability } from "../lib/api";
import { lookup, useT } from "../lib/i18n";
import { ProvenanceChip } from "./ProvenanceChip";
import { RiskDial } from "./RiskDial";

export function ReachabilityCard({
  unitId,
  onBack,
}: {
  unitId: number;
  onBack: () => void;
}) {
  const { t } = useT();
  const [reach, setReach] = useState<Reachability | null>(null);
  const [vuln, setVuln] = useState<Vulnerability | null>(null);
  const [risk, setRisk] = useState<UnitRisk | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      setError(null);
      setReach(null);
      setVuln(null);
      setRisk(null);
      const [r, v, k] = await Promise.allSettled([
        endpoints.reachability(unitId),
        endpoints.vulnerability(unitId),
        endpoints.risk(unitId),
      ]);
      if (r.status === "fulfilled") setReach(r.value);
      if (v.status === "fulfilled") setVuln(v.value);
      if (k.status === "fulfilled") setRisk(k.value);
      if (r.status === "rejected" && v.status === "rejected" && k.status === "rejected") {
        const err = r.reason;
        if (err instanceof ApiError && err.code === "unit_scope") setError(t("unit.outside"));
        else if (err instanceof ApiError && err.status === 404) setError(t("unit.none"));
        else if (err instanceof ApiError && err.status === 403) setError(t("unit.forbidden"));
        else setError(t("unit.loadError"));
      }
    })();
  }, [unitId, t]);

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("unit.kicker")}</p>
          <h2>{reach?.name ?? vuln?.name ?? `${t("unit.kicker")} ${unitId}`}</h2>
        </div>
        <button className="btn btn--ghost" onClick={onBack}>{t("unit.back")}</button>
      </header>
      {error && <p className="danger" role="alert">{error}</p>}
      {reach && (
        <section className="kpis dial-row" aria-label={t("board.reach")}>
          <RiskDial
            value={reach.recipient_reach_pct}
            label={t("unit.ofRegistered")}
            note={`${reach.reached_recipients}/${reach.registered_recipients}`}
          />
          <RiskDial
            value={reach.population_reach_pct}
            label={t("unit.ofPopulation")}
            note={reach.estimated_population ? String(reach.estimated_population) : t("unit.noPop")}
          />
        </section>
      )}
      {vuln && (
        <section className="panel detail__box">
          <h3>{t("unit.hard")}</h3>
          <p>{lookup(t, "fallback", vuln.recommended_fallback)}</p>
          <ul>
            {vuln.primary_factors.map((f) => (
              <li key={f}>{lookup(t, "factor", f)}</li>
            ))}
          </ul>
          {vuln.primary_factors.includes("no_relay_coverage") && (
            <ProvenanceChip kind="humanRelay" />
          )}
        </section>
      )}
      {risk && (
        <section className="panel detail__box dial-row">
          <h3>{t("unit.risk")}</h3>
          {risk.is_bootstrap && <ProvenanceChip kind="bootstrapML" />}
          <RiskDial
            value={risk.risk_score}
            label={t("unit.risk")}
            note={risk.recommended_action ?? undefined}
          />
          <p className="muted">{risk.disclosure}</p>
          <ul>
            {risk.top_factors.map((factor) => (
              <li key={factor.factor}>
                {lookup(t, "factor", factor.factor)}: {String(factor.value)}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
