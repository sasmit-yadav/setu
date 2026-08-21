import { useEffect, useState } from "react";
import { ApiError, endpoints, type Reachability, type UnitRisk, type Vulnerability } from "../lib/api";
import { ProvenanceChip } from "./ProvenanceChip";
import { RiskDial } from "./RiskDial";

function unitLoadError(err: unknown): string {
  if (err instanceof ApiError && err.code === "unit_scope") {
    return "This village is outside your assigned unit.";
  }
  if (err instanceof ApiError && err.status === 404) {
    return "This unit has no reachability record yet.";
  }
  if (err instanceof ApiError && err.status === 403) {
    return "You do not have access to this unit.";
  }
  return "Could not load this unit.";
}

export function ReachabilityCard({
  unitId,
  onBack,
}: {
  unitId: number;
  onBack: () => void;
}) {
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
        setError(unitLoadError(r.reason));
      }
    })();
  }, [unitId]);

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Unit</p>
          <h2>{reach?.name ?? vuln?.name ?? `Unit ${unitId}`}</h2>
        </div>
        <button className="btn btn--ghost" onClick={onBack}>Back</button>
      </header>
      {error && <p className="danger" role="alert">{error}</p>}
      {reach && (
        <section className="kpis dial-row" aria-label="Reachability">
          <RiskDial
            value={reach.recipient_reach_pct}
            label="Of registered"
            note={`ADM${reach.geometry_level} · ${reach.reached_recipients}/${reach.registered_recipients}`}
          />
          <RiskDial
            value={reach.population_reach_pct}
            label="Of population"
            note={reach.estimated_population ? String(reach.estimated_population) : "no population"}
          />
        </section>
      )}
      {vuln && (
        <section className="panel detail__box">
          <h3>Communication vulnerability</h3>
          <p>{vuln.recommended_fallback}</p>
          <ul>
            {vuln.primary_factors.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          {vuln.primary_factors.includes("no_relay_coverage") && (
            <ProvenanceChip kind="humanRelay" />
          )}
        </section>
      )}
      {risk && (
        <section className="panel detail__box dial-row">
          <h3>Reach-risk</h3>
          {risk.is_bootstrap && <ProvenanceChip kind="bootstrapML" />}
          <RiskDial
            value={risk.risk_score}
            label="Reach-risk"
            note={risk.recommended_action ?? undefined}
          />
          <p className="muted">{risk.disclosure}</p>
          <ul>
            {risk.top_factors.map((factor) => (
              <li key={factor.factor} className="mono">
                {factor.factor}: {String(factor.value)}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
