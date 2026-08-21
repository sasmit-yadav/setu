import { useEffect, useState } from "react";
import { endpoints } from "../lib/api";
import { lookup, useT } from "../lib/i18n";

export function Methodology() {
  const { t } = useT();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await endpoints.methodology());
      } catch {
        setError(t("method.loadError"));
      }
    })();
  }, [t]);

  const capability = Array.isArray(data?.channel_capability) ? data.channel_capability : [];
  const limitations = Array.isArray(data?.limitations) ? data.limitations : [];
  const models = Array.isArray(data?.models) ? data.models : [];

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("method.kicker")}</p>
          <h2>{t("method.title")}</h2>
        </div>
      </header>
      {error && <p className="danger" role="alert" aria-live="polite">{error}</p>}
      <section className="panel detail__box" aria-label={t("method.channels")}>
        <h3>{t("method.channels")}</h3>
        <table className="method-table">
          <caption className="sr-only">{t("method.channels")}</caption>
          <thead>
            <tr>
              <th>{t("method.colChannel")}</th>
              <th>{t("method.colTier")}</th>
              <th>{t("method.colSupported")}</th>
              <th>{t("method.colEvidence")}</th>
              <th>{t("method.colReason")}</th>
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
                  <td>{lookup(t, "channel", item.channel_code)}</td>
                  <td>{lookup(t, "ladder", item.tier)}</td>
                  <td>{item.supported ? t("method.yes") : t("method.no")}</td>
                  <td className="muted">{item.evidence_source ?? "—"}</td>
                  <td className="muted">{item.not_applicable_reason ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      <section className="panel detail__box" aria-label={t("method.models")}>
        <h3>{t("method.models")}</h3>
        <table className="method-table">
          <caption className="sr-only">{t("method.models")}</caption>
          <thead>
            <tr>
              <th>{t("method.colName")}</th>
              <th>{t("method.colVersion")}</th>
              <th>{t("method.colKind")}</th>
              <th>{t("method.colMetrics")}</th>
            </tr>
          </thead>
          <tbody>
            {models.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">{t("method.noModels")}</td>
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
                    <td>{item.name}</td>
                    <td className="mono">{item.version}</td>
                    <td>{item.is_bootstrap ? t("method.guess") : t("method.trained")}</td>
                    <td>
                      {precision != null || recall != null ? (
                        <span>
                          n={String(n ?? "—")} · P={String(precision ?? "—")} · R={String(recall ?? "—")} · F1={String(f1 ?? "—")}
                        </span>
                      ) : (
                        <span className="muted">{disclosure ? String(disclosure) : t("method.noModels")}</span>
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
      <section className="panel detail__box" aria-label={t("method.limits")}>
        <h3>{t("method.limits")}</h3>
        <ul>
          {limitations.map((line) => (
            <li key={String(line)}>{String(line)}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
