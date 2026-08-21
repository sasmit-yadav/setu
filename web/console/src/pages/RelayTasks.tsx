import { useEffect, useState } from "react";
import { endpoints, type RelayTask } from "../lib/api";
import { SeverityBadge } from "../components/SeverityBadge";
import { ProvenanceChip } from "../components/ProvenanceChip";

export function RelayTasks() {
  const [rows, setRows] = useState<RelayTask[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function load() {
    try {
      setRows(await endpoints.relayTasks());
      setError(null);
    } catch {
      setError("Could not load relay tasks.");
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
      setError("Could not confirm this relay.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Last resort</p>
          <h2>Relay tasks</h2>
        </div>
        <ProvenanceChip kind="humanRelay" />
      </header>
      {error && <p className="danger" role="alert">{error}</p>}
      <section className="panel table" aria-label="Relay tasks">
        <div className="table__head relay__head" role="row">
          <span>Unit</span>
          <span>Severity</span>
          <span>Headline</span>
          <span>State</span>
          <span />
        </div>
        {rows.length === 0 && <p className="muted table__empty">No open relay tasks.</p>}
        {rows.map((row) => (
          <div key={row.id} className="table__row relay__row" role="row">
            <span>{row.unit_name}</span>
            <SeverityBadge severity={row.severity} />
            <span>{row.headline}</span>
            <span className="mono muted">{row.state}</span>
            <button
              className="btn btn--approve"
              disabled={busyId === row.id}
              onClick={() => void confirm(row.id)}
            >
              {busyId === row.id ? "Confirming…" : "Confirm in person"}
            </button>
          </div>
        ))}
      </section>
    </div>
  );
}
