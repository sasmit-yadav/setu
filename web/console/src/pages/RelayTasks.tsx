import { useEffect, useState } from "react";
import { endpoints, type RelayTask } from "../lib/api";
import { lookup, useT } from "../lib/i18n";
import { SeverityBadge } from "../components/SeverityBadge";
import { ProvenanceChip } from "../components/ProvenanceChip";

export function RelayTasks() {
  const { t } = useT();
  const [rows, setRows] = useState<RelayTask[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function load() {
    try {
      setRows(await endpoints.relayTasks());
      setError(null);
    } catch {
      setError(t("relay.loadError"));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function confirm(id: number) {
    setBusyId(id);
    try {
      await endpoints.confirmRelayTask(id);
      await load();
    } catch {
      setError(t("relay.confirmFail"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("relay.kicker")}</p>
          <h2>{t("relay.title")}</h2>
        </div>
        <ProvenanceChip kind="humanRelay" />
      </header>
      <p className="lede">{t("relay.lede")}</p>
      {error && <p className="danger" role="alert">{error}</p>}
      <section className="panel table" aria-label={t("relay.title")}>
        <div className="table__head relay__head" role="row">
          <span>{t("relay.colUnit")}</span>
          <span>{t("relay.colSeverity")}</span>
          <span>{t("relay.colHeadline")}</span>
          <span>{t("relay.colState")}</span>
          <span />
        </div>
        {rows.length === 0 && <p className="muted table__empty">{t("relay.empty")}</p>}
        {rows.map((row) => (
          <div key={row.id} className="table__row relay__row" role="row">
            <span>{row.unit_name}</span>
            <SeverityBadge severity={row.severity} />
            <span>{row.headline}</span>
            <span className="muted">{lookup(t, "state", row.state)}</span>
            <button
              className="btn btn--approve"
              disabled={busyId === row.id}
              onClick={() => void confirm(row.id)}
            >
              {busyId === row.id ? t("relay.confirming") : t("relay.confirm")}
            </button>
          </div>
        ))}
      </section>
    </div>
  );
}
