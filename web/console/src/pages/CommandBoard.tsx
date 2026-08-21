import { useEffect, useState } from "react";
import {
  ApiError,
  endpoints,
  type AfterAction,
  type IncidentSummary,
} from "../lib/api";
import { lookup, useT } from "../lib/i18n";
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

function pct(value: number | null, t: (k: string) => string): string {
  return value == null ? t("common.nA") : `${value}%`;
}

export function CommandBoard({
  onIncident,
}: {
  onIncident: (id: number) => void;
}) {
  const { t } = useT();
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
      setError(t("board.loadError"));
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
            ? t("board.forbidden")
            : t("board.loadError"),
        );
      }
      if (nextAfter.status === "fulfilled") setAfter(nextAfter.value);
    })();
  }, [selected, t]);

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
          <p className="screen__kicker">{t("board.kicker")}</p>
          <h2>{t("board.title")}</h2>
        </div>
        {selected != null && (
          <button className="btn btn--ghost" onClick={() => onIncident(selected)}>
            {t("board.openEmergency")}
          </button>
        )}
      </header>
      {error && (
        <p className="danger" role="alert" aria-live="polite">
          {error}
        </p>
      )}
      <section className="kpis" aria-label={t("board.totals")}>
        <Kpi label={t("board.openIncidents")} value={incidents.length} />
        {board && (
          <>
            <Kpi
              label={t("board.queueDepth")}
              value={board.queue_depth}
              tone={board.queue_depth ? "warn" : "ok"}
            />
            <Kpi
              label={t("board.humanConfirms")}
              value={board.human_confirmations}
              tone={board.human_confirmations ? "info" : undefined}
            />
            <Kpi
              label={t("board.noRunner")}
              value={dark.length}
              tone={dark.length ? "danger" : "ok"}
            />
          </>
        )}
      </section>

      <section className="panel table board__incidents" aria-label={t("board.openIncidents")}>
        <div className="table__head board__incidents-head">
          <span>{t("board.colLabel")}</span>
          <span>{t("board.colType")}</span>
          <span>{t("board.colStatus")}</span>
          <span>{t("board.colOpened")}</span>
        </div>
        {!incidents.length && (
          <p className="muted table__empty">{t("board.empty")}</p>
        )}
        {incidents.map((row) => (
          <button
            key={row.id}
            className={`table__row board__incidents-row${selected === row.id ? " is-selected" : ""}`}
            onClick={() => setSelected(row.id)}
            aria-pressed={selected === row.id}
            aria-label={t("board.selectIncident", { label: row.label })}
          >
            <span>{row.label}</span>
            <span className="muted">{row.incident_type}</span>
            <span>{lookup(t, "life", row.status)}</span>
            <time className="mono muted">{row.opened_at}</time>
          </button>
        ))}
      </section>

      {current && (
        <p className="board__ribbon muted">
          {t("board.ribbon", {
            label: current.label,
            status: lookup(t, "life", current.status),
            source: current.origin_source,
            versions: current.version_count,
          })}
        </p>
      )}

      <div className="board__cop">
        <section className="panel detail__box" aria-label={t("board.hardest")}>
          <h3>{t("board.hardest")}</h3>
          <p className="muted">
            {worst.length ? t("board.hardestNote", { n: worst.length }) : t("board.hardestEmpty")}
          </p>
          <ul className="board__cards">
            {worst.map((item) => (
              <li key={item.unit_id} className="board__card">
                <RiskDial
                  value={item.historical_reach_pct}
                  label={item.name}
                  note={t("board.fallback", {
                    action: lookup(t, "fallback", item.recommended_fallback),
                  })}
                />
                <span className="muted">
                  {item.primary_factors.map((f) => lookup(t, "factor", f)).join(", ")}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel detail__box" aria-label={t("board.gaps")}>
          <h3>{t("board.gaps")}</h3>
          {!dark.length ? (
            <p className="ok">{t("board.gapsOk")}</p>
          ) : (
            <ul className="board__gaps">
              {dark.map((item) => (
                <li key={item.unit_id}>
                  <strong>{item.name}</strong>
                  <span className="danger"> {t("board.gapsBad")}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel detail__box" aria-label={t("board.reach")}>
          <h3>{t("board.reach")}</h3>
          <p className="muted">{t("board.reachNote", { n: reach.length })}</p>
          <button className="btn btn--ghost" onClick={() => setShowReach((open) => !open)}>
            {showReach ? t("board.hideRows") : t("board.showRows")}
          </button>
          {showReach && (
            <ul>
              {reach.map((item) => (
                <li key={item.unit_id}>
                  {t("board.reachRow", {
                    name: item.name,
                    reg: pct(item.recipient_reach_pct, t),
                    pop: pct(item.population_reach_pct, t),
                  })}
                </li>
              ))}
            </ul>
          )}
          {Boolean(board?.human_confirmations) && <ProvenanceChip kind="humanRelay" />}
        </section>

        <section className="panel detail__box" aria-label={t("board.channels")}>
          <h3>{t("board.channels")}</h3>
          {!channels.length ? (
            <p className="muted">{t("board.channelsEmpty")}</p>
          ) : (
            <ul className="board__channels">
              {channels.map((item) => (
                <li key={item.channel_code} className="board__channel">
                  <strong>{lookup(t, "channel", item.channel_code)}</strong>
                  <span>{t("board.channelLine", { n: item.deliveries })}</span>
                  <span className="muted">{t("board.channelSim", { n: item.simulated })}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel detail__box board__recs" aria-label={t("board.after")}>
          <h3>{t("board.after")}</h3>
          {!recs.length ? (
            <p className="muted">{t("board.afterEmpty")}</p>
          ) : (
            <ul className="board__rec-list">
              {recs.map((rec) => (
                <li key={rec.id}>
                  <p>{rec.recommendation}</p>
                  <p className="muted">
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
