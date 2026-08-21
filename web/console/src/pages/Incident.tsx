import { useEffect, useState } from "react";
import {
  ApiError,
  endpoints,
  type AfterAction,
  type IncidentDetail,
  type TimelineEvent,
} from "../lib/api";
import { SeverityBadge } from "../components/SeverityBadge";

export function IncidentPage({
  id,
  onBack,
  onAlert,
  canClose,
}: {
  id: number;
  onBack: () => void;
  onAlert: (alertId: number) => void;
  canClose?: boolean;
}) {
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [after, setAfter] = useState<AfterAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const [d, t, a] = await Promise.allSettled([
      endpoints.incident(id),
      endpoints.timeline(id),
      endpoints.afterAction(id),
    ]);
    if (d.status === "fulfilled") {
      setDetail(d.value);
      setError(null);
    } else {
      setDetail(null);
      setError(d.reason instanceof ApiError && d.reason.status === 403
        ? "You do not have access to this incident."
        : "Could not load incident.");
    }
    if (t.status === "fulfilled") setEvents(t.value);
    if (a.status === "fulfilled") setAfter(a.value);
  }

  useEffect(() => {
    void load();
  }, [id]);

  async function closeIncident() {
    setBusy(true);
    try {
      await endpoints.closeIncident(id);
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("Only a state administrator can close an incident.");
      } else {
        setError("Could not close the incident.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (error && !detail) return <p className="danger" role="alert">{error}</p>;
  if (!detail) return <p className="muted">Loading…</p>;

  const approvals = events.filter((event) => event.event_type.includes("approv"));
  const recs = after?.recommendations ?? [];
  const closed = detail.status === "closed";

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Incident</p>
          <h2>{detail.label}</h2>
        </div>
        <button className="btn btn--ghost" onClick={onBack} aria-label="Back to board">Back</button>
        {canClose && !closed && (
          <button className="btn btn--danger" disabled={busy} onClick={() => void closeIncident()} aria-label="Close incident">
            {busy ? "Closing…" : "Close incident"}
          </button>
        )}
      </header>
      {error && (
        <p className="danger" role="alert">{error}</p>
      )}
      <p className="muted">{detail.origin_source} · {detail.status} · opened {detail.opened_at}</p>

      <section className="panel detail__box" aria-label="Version chain">
        <h3>Version chain</h3>
        <ol className="version-chain">
          {detail.versions.map((v) => {
            const active = v.lifecycle_status === "active";
            return (
              <li key={v.id} className={`version-chain__item${active ? " is-active" : ""}`}>
                <button className="btn btn--ghost" onClick={() => onAlert(v.id)}>
                  v{v.version_number} {v.lifecycle_status.toUpperCase()}
                </button>
                <SeverityBadge severity={v.severity} />
                {v.change_reason && <span className="muted"> — {v.change_reason}</span>}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="panel detail__box" aria-label="Approval trail">
        <h3>Approval trail</h3>
        {approvals.length === 0 ? (
          <p className="muted">No approval events on this incident yet.</p>
        ) : (
          <ol className="timeline timeline--rail">
            {approvals.map((event) => (
              <li key={event.id}>
                <time className="mono muted" dateTime={event.occurred_at}>{event.occurred_at}</time>
                <strong>{event.event_type}</strong>
                {event.actor && <span className="muted"> · {event.actor}</span>}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="panel detail__box" aria-label="After-action recommendations">
        <h3>After-action</h3>
        {recs.length === 0 ? (
          <p className="muted">No recommendations yet.</p>
        ) : (
          <ul className="board__rec-list">
            {recs.map((rec) => (
              <li key={rec.id}>
                <p>{rec.recommendation}</p>
                <p className="mono muted">
                  {rec.measurement}: {rec.value}
                  {rec.denominator != null ? ` / ${rec.denominator}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel detail__box" aria-label="Incident timeline">
        <h3>Timeline</h3>
        <ol className="timeline timeline--rail">
          {events.map((event) => (
            <li key={event.id}>
              <time className="mono muted" dateTime={event.occurred_at}>{event.occurred_at}</time>
              <strong>{event.event_type}</strong>
              {event.actor && <span className="muted"> · {event.actor}</span>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
