/** D1f/D2f — Live Operations.
 *
 * References (Part 0.4.6): Linear's list view for the table (virtualised
 * density without visual noise), and Apex/Valorant's kill-feed for the live
 * event rail — Part 0.5 says the delivery feed "scrolls like a kill-feed along
 * one edge of the Live Operations screen, one line per acknowledgement as it
 * lands".
 *
 * Progressive disclosure (Part 0.4.3): this screen shows the aggregate first —
 * the KPI strip — and row-level detail on demand. You click through to an
 * alert to see its ladder; the ladder is not inlined 250 times here.
 */

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { endpoints, type AlertSummary } from "../lib/api";
import { SeverityBadge } from "../components/SeverityBadge";
import { Kpi } from "../components/Kpi";
import { ProvenanceChip } from "../components/ProvenanceChip";

function relative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (Math.abs(mins) < 60) return `${mins}m`;
  const hrs = Math.round(mins / 60);
  if (Math.abs(hrs) < 48) return `${hrs}h`;
  return `${Math.round(hrs / 24)}d`;
}

export function LiveOps({ onOpen }: { onOpen: (id: number) => void }) {
  const [alerts, setAlerts] = useState<AlertSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setAlerts(await endpoints.alerts(100));
      setError(null);
    } catch {
      setError("Could not load alerts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const active = alerts.filter((a) => a.lifecycle_status === "active");
  const drafts = alerts.filter((a) => a.lifecycle_status === "draft");
  const extreme = alerts.filter((a) => a.severity === "extreme");

  return (
    <div className="screen">
      <header className="screen__head">
        <h2>Live Operations</h2>
        <button className="btn btn--ghost" onClick={() => void load()} aria-label="Refresh">
          <RefreshCw size={14} aria-hidden /> Refresh
        </button>
      </header>

      {/* Aggregate first. Counts are mono + tabular-nums so the strip does not
          reflow when a number changes width. */}
      <section className="kpis" aria-label="Summary">
        <Kpi label="Alerts" value={alerts.length} />
        <Kpi label="Active" value={active.length} tone="info" />
        <Kpi label="Drafts" value={drafts.length} />
        <Kpi
          label="Extreme"
          value={extreme.length}
          tone={extreme.length ? "danger" : undefined}
        />
      </section>

      {error && <p className="danger" role="alert">{error}</p>}

      <section className="panel table" aria-label="Alerts">
        <div className="table__head" role="row">
          <span role="columnheader">ID</span>
          <span role="columnheader">Severity</span>
          <span role="columnheader">Headline</span>
          <span role="columnheader">Source</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Effective</span>
        </div>
        <div className="table__body">
          {loading && <p className="muted table__empty">Loading…</p>}
          {!loading && alerts.length === 0 && (
            <p className="muted table__empty">No alerts.</p>
          )}
          {alerts.map((a) => (
            <button
              key={a.id}
              className="table__row"
              onClick={() => onOpen(a.id)}
              role="row"
            >
              <span className="mono muted">{a.id}</span>
              <SeverityBadge severity={a.severity} />
              <span className="table__headline">{a.headline}</span>
              <span className="mono muted">
                {a.source_id}
                {/* Rule 12 made visible: an authoritative feed dispatches
                    without a human, so the officer should be able to see at a
                    glance which alerts those are. */}
                {(a.source_id === "usgs" || a.source_id === "gdacs") && (
                  <> <ProvenanceChip kind="authoritative" /></>
                )}
              </span>
              <span className={`status status--${a.lifecycle_status}`}>
                {a.lifecycle_status}
              </span>
              <time className="mono muted" dateTime={a.effective_at}>
                {relative(a.effective_at)}
              </time>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
