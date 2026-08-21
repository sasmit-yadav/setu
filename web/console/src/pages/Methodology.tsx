import { useEffect, useState } from "react";
import { endpoints } from "../lib/api";

export function Methodology() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await endpoints.methodology());
      } catch {
        setError("Could not load methodology.");
      }
    })();
  }, []);

  const capability = Array.isArray(data?.channel_capability) ? data.channel_capability : [];
  const limitations = Array.isArray(data?.limitations) ? data.limitations : [];
  const models = Array.isArray(data?.models) ? data.models : [];

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Accountability</p>
          <h2>Methodology</h2>
        </div>
      </header>
      {error && <p className="danger" role="alert" aria-live="polite">{error}</p>}
      <section className="panel detail__box" aria-label="Channel capability">
        <h3>Channel capability</h3>
        <table className="method-table">
          <caption className="sr-only">Channel assurance capability by tier</caption>
          <thead>
            <tr>
              <th>Channel</th>
              <th>Tier</th>
              <th>Supported</th>
              <th>Evidence</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {capability.map((row, index) => {
              const item = row as {
                channel_code: string;
                tier: string;
                supported: boolean;
                evidence_source: string | null;
                not_applicable_reason: string | null;
              };
              return (
                <tr key={`${item.channel_code}-${item.tier}-${index}`}>
                  <td className="mono">{item.channel_code}</td>
                  <td>{item.tier}</td>
                  <td>{item.supported ? "yes" : "no"}</td>
                  <td className="muted">{item.evidence_source ?? "—"}</td>
                  <td className="muted">{item.not_applicable_reason ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      <section className="panel detail__box" aria-label="Published models">
        <h3>Models</h3>
        <table className="method-table">
          <caption className="sr-only">Registered models with published metrics</caption>
          <thead>
            <tr>
              <th>Name</th>
              <th>Version</th>
              <th>Bootstrap</th>
              <th>Metrics</th>
            </tr>
          </thead>
          <tbody>
            {models.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">No models registered yet. Run python scripts/eval_models.py after seeding.</td>
              </tr>
            ) : (
              models.map((row, index) => {
                const item = row as {
                  name: string;
                  version: string;
                  is_bootstrap: boolean;
                  metrics: Record<string, unknown> | null;
                };
                const metrics = item.metrics ?? {};
                const precision = metrics.precision;
                const recall = metrics.recall;
                const f1 = metrics.f1;
                const n = metrics.n ?? metrics.held_out_n;
                const disclosure = metrics.disclosure;
                return (
                  <tr key={`${item.name}-${item.version}-${index}`}>
                    <td className="mono">{item.name}</td>
                    <td className="mono">{item.version}</td>
                    <td>{item.is_bootstrap ? "bootstrap" : "trained"}</td>
                    <td>
                      {precision != null || recall != null ? (
                        <span>
                          n={String(n ?? "—")} · P={String(precision ?? "—")} · R={String(recall ?? "—")} · F1={String(f1 ?? "—")}
                        </span>
                      ) : (
                        <span className="muted">{disclosure ? String(disclosure) : "no held-out metrics yet"}</span>
                      )}
                      {disclosure ? <p className="muted">{String(disclosure)}</p> : null}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </section>
      <section className="panel detail__box" aria-label="Published limitations">
        <h3>Limitations</h3>
        <ul>
          {limitations.map((line) => (
            <li key={String(line)}>{String(line)}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
