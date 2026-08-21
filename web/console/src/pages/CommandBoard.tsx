import { useEffect, useState } from "react";
import {
  ApiError,
  endpoints,
  type AfterAction,
  type IncidentSummary,
} from "../lib/api";
import { Kpi } from "../components/Kpi";
import { ProvenanceChip } from "../components/ProvenanceChip";
import { RiskDial } from "../components/RiskDial";
import { useOpsSocket } from "../lib/useOpsSocket";

type BoardPayload = {
  incident_id: number;
  queue_depth: number;
  human_confirmations: number;
  reachability: Array<{
    unit_id: number;
    name: string;
    geometry_level: number;
    recipient_reach_pct: number | null;
    population_reach_pct: number | null;
  }>;
  worst_units: Array<{
    unit_id: number;
    name: string;
    primary_factors: string[];
    recommended_fallback: string;
    historical_reach_pct: number | null;
  }>;
  no_relay_coverage: Array<{ unit_id: number; name: string }>;
  channels: Array<{
    channel_code: string;
    deliveries: number;
    simulated: number;
    max_assurance: number;
  }>;
};

function pct(value: number | null): string {
  return value == null ? "n/a" : `${value}%`;
}

export function CommandBoard({
  onIncident,
}: {
  onIncident: (id: number) => void;
}) {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [board, setBoard] = useState<BoardPayload | null>(null);
  const [after, setAfter] = useState<AfterAction | null>(null);
  const [showReach, setShowReach] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadList() {
    try {
      const rows = await endpoints.incidents();
      setIncidents(rows);
      setSelected((current) => {
        if (current != null && rows.some((row) => row.id === current)) return current;
        const [first] = rows;
        return first ? first.id : null;
      });
      setError(null);
    } catch {
      setError("Could not load the command board.");
    }
  }

  useEffect(() => {
    void loadList();
  }, []);
  useOpsSocket(() => void loadList());

  useEffect(() => {
    if (selected == null) {
      setBoard(null);
      setAfter(null);
      return;
    }
    void (async () => {
      const [nextBoard, nextAfter] = await Promise.allSettled([
        endpoints.board(selected) as Promise<BoardPayload>,
        endpoints.afterAction(selected),
      ]);
      if (nextBoard.status === "fulfilled") {
        setBoard(nextBoard.value);
        setError(null);
      } else {
        setError(
          nextBoard.reason instanceof ApiError && nextBoard.reason.status === 403
            ? "You do not have access to this board."
            : "Could not load the command board.",
        );
      }
      if (nextAfter.status === "fulfilled") setAfter(nextAfter.value);
    })();
  }, [selected]);

  const reach = board?.reachability ?? [];
  const dark = board?.no_relay_coverage ?? [];
  const worst = board?.worst_units ?? [];
  const channels = board?.channels ?? [];
  const current = incidents.find((row) => row.id === selected);
  const recs = after?.recommendations ?? [];

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Common operating picture</p>
          <h2>Command Board</h2>
        </div>
        {selected != null && (
          <button className="btn btn--ghost" onClick={() => onIncident(selected)}>
            Open incident
          </button>
        )}
      </header>
      {error && (
        <p className="danger" role="alert" aria-live="polite">
          {error}
        </p>
      )}
      <section className="kpis" aria-label="Board totals">
        <Kpi label="Open incidents" value={incidents.length} />
        {board && (
          <>
            <Kpi
              label="Queue depth"
              value={board.queue_depth}
              tone={board.queue_depth ? "warn" : "ok"}
            />
            <Kpi
              label="HUMAN confirmations"
              value={board.human_confirmations}
              tone={board.human_confirmations ? "info" : undefined}
            />
            <Kpi
              label="No relay coverage"
              value={dark.length}
              tone={dark.length ? "danger" : "ok"}
            />
          </>
        )}
      </section>

      <section className="panel table board__incidents" aria-label="Incidents">
        <div className="table__head board__incidents-head">
          <span>Label</span>
          <span>Type</span>
          <span>Status</span>
          <span>Opened</span>
        </div>
        {!incidents.length && (
          <p className="muted table__empty">No incidents.</p>
        )}
        {incidents.map((row) => (
          <button
            key={row.id}
            className={`table__row board__incidents-row${selected === row.id ? " is-selected" : ""}`}
            onClick={() => setSelected(row.id)}
            aria-pressed={selected === row.id}
            aria-label={`Select incident ${row.label}`}
          >
            <span>{row.label}</span>
            <span className="mono muted">{row.incident_type}</span>
            <span>{row.status}</span>
            <time className="mono muted">{row.opened_at}</time>
          </button>
        ))}
      </section>

      {current && (
        <p className="board__ribbon muted">
          {current.label} · {current.status} · {current.origin_source} · versions {current.version_count}
        </p>
      )}

      <div className="board__cop">
        <section className="panel detail__box" aria-label="Highest-risk units">
          <h3>Highest-risk units</h3>
          <p className="muted">
            {worst.length ? `${worst.length} units ranked from communication vulnerability.` : "No vulnerability ranking for this incident yet."}
          </p>
          <ul className="board__cards">
            {worst.map((item) => (
              <li key={item.unit_id} className="board__card">
                <RiskDial
                  value={item.historical_reach_pct}
                  label={item.name}
                  note={`fallback ${item.recommended_fallback}`}
                />
                <span className="muted">{item.primary_factors.join(", ")}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel detail__box" aria-label="Units with no relay coverage">
          <h3>Last-resort gaps</h3>
          {!dark.length ? (
            <p className="ok">Every listed unit has a registered relay node.</p>
          ) : (
            <ul className="board__gaps">
              {dark.map((item) => (
                <li key={item.unit_id}>
                  <strong>{item.name}</strong>
                  <span className="danger"> unreachable — no relay coverage</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel detail__box" aria-label="Reachability">
          <h3>Reachability</h3>
          <p className="muted">
            {reach.length} units with a figure. Every percentage is labelled with its geometry level.
          </p>
          <button className="btn btn--ghost" onClick={() => setShowReach((open) => !open)}>
            {showReach ? "Hide unit rows" : "Show unit rows"}
          </button>
          {showReach && (
            <ul>
              {reach.map((item) => (
                <li key={item.unit_id}>
                  {item.name} · ADM{item.geometry_level} · registered {pct(item.recipient_reach_pct)} · population {pct(item.population_reach_pct)}
                </li>
              ))}
            </ul>
          )}
          {Boolean(board?.human_confirmations) && <ProvenanceChip kind="humanRelay" />}
        </section>

        <section className="panel detail__box" aria-label="Per-channel assurance">
          <h3>Per-channel assurance</h3>
          {!channels.length ? (
            <p className="muted">No deliveries on this incident yet.</p>
          ) : (
            <ul className="board__channels">
              {channels.map((item) => (
                <li key={item.channel_code} className="board__channel">
                  <strong className="mono">{item.channel_code}</strong>
                  <span>{item.deliveries} deliveries</span>
                  <span className="muted">sim {item.simulated}</span>
                  <span className="muted">max tier {item.max_assurance}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel detail__box board__recs" aria-label="After-action recommendations">
          <h3>After-action</h3>
          {!recs.length ? (
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
      </div>
    </div>
  );
}
