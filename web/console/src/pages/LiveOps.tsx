import { useCallback, useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { PenLine, RefreshCw } from "lucide-react";
import {
  endpoints,
  type AlertSummary,
  type MapPayload,
  type OpsFeedItem,
  type OpsSummary,
  type PublicConfig,
} from "../lib/api";
import { SeverityBadge } from "../components/SeverityBadge";
import { ProvenanceChip } from "../components/ProvenanceChip";
import { Kpi } from "../components/Kpi";
import { LiveMap } from "../components/LiveMap";
import { useOpsSocket } from "../lib/useOpsSocket";

function relative(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60_000);
  const hourMins = 60;
  const twoDayHours = 48;
  if (Math.abs(mins) < hourMins) return `${mins}m`;
  const hrs = Math.round(mins / hourMins);
  if (Math.abs(hrs) < twoDayHours) return `${hrs}h`;
  return `${Math.round(hrs / 24)}d`;
}

function feedLabel(eventType: string): string {
  if (eventType === "acknowledged") return "acknowledged";
  if (eventType === "device_delivered") return "device delivered";
  if (eventType === "notification_opened") return "opened";
  if (eventType === "citizen_response") return "response";
  return eventType;
}

export function LiveOps({
  onOpen,
  onCompose,
  onUnit,
}: {
  onOpen: (id: number) => void;
  onCompose: () => void;
  onUnit: (id: number) => void;
}) {
  const [alerts, setAlerts] = useState<AlertSummary[]>([]);
  const [map, setMap] = useState<MapPayload | null>(null);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [feed, setFeed] = useState<OpsFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const parentRef = useRef<HTMLDivElement>(null);
  const feedHeadRef = useRef<string | null>(null);
  const [freshHead, setFreshHead] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [nextAlerts, nextMap, nextCfg, nextSummary, nextFeed] = await Promise.all([
        endpoints.alerts(),
        endpoints.map(),
        endpoints.publicConfig(),
        endpoints.opsSummary(),
        endpoints.opsFeed(),
      ]);
      setAlerts(nextAlerts);
      setMap(nextMap);
      setCfg(nextCfg);
      setSummary(nextSummary);
      setFeed(nextFeed);
      const head = nextFeed[0];
      const headKey = head
        ? `${head.delivery_id}-${head.event_type}-${head.occurred_at}`
        : null;
      if (headKey && feedHeadRef.current && feedHeadRef.current !== headKey) {
        setFreshHead(headKey);
      }
      feedHeadRef.current = headKey;
      setError(null);
    } catch {
      setError("Could not load live operations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);
  useOpsSocket(() => void load());

  const virtualizer = useVirtualizer({
    count: alerts.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 44,
    overscan: 12,
  });

  const tileSource = String(cfg?.["map.tile_source"] ?? map?.tile_source ?? "");

  return (
    <div className="screen screen--wide">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">Live picture</p>
          <h2>Live Operations</h2>
        </div>
        <button className="btn btn--primary" onClick={onCompose}>
          <PenLine size={14} aria-hidden /> Compose
        </button>
        <button className="btn btn--ghost" onClick={() => void load()} aria-label="Refresh">
          <RefreshCw size={14} aria-hidden /> Refresh
        </button>
      </header>

      <div className="trouble" aria-label="Active alerts by severity">
        <span className="trouble__label muted">Where is trouble</span>
        {alerts
          .filter((a) => a.lifecycle_status === "active")
          .map((a) => (
            <button
              key={a.id}
              className={`trouble__tick trouble__tick--${a.severity}`}
              onClick={() => onOpen(a.id)}
              title={a.headline}
            >
              <SeverityBadge severity={a.severity} />
              <span className="sr-only">{a.headline}</span>
            </button>
          ))}
      </div>
      {summary && (
        <section className="kpis" aria-label="Summary">
          <Kpi label="Targeted" value={summary.targeted} />
          <Kpi
            label="Delivered"
            value={summary.delivered}
            tone="info"
            note={summary.delivered_note}
          />
          <Kpi
            label="Acknowledged"
            value={summary.acknowledged}
            tone={summary.acknowledged ? "ok" : undefined}
            note={summary.acknowledged_note}
          />
          <Kpi
            label="At-risk"
            value={summary.at_risk}
            tone={summary.at_risk ? "danger" : "ok"}
            note={summary.at_risk_note}
          />
        </section>
      )}

      {tileSource !== "pmtiles_local" && (
        <p className="muted" role="status">
          Basemap is {tileSource || "hosted"}. Gate 3 needs map.tile_source=pmtiles_local and a local .pmtiles file.
        </p>
      )}
      {error && <p className="danger" role="alert">{error}</p>}

      <div className="live-split">
        <div className="live-map-wrap">
          <LiveMap payload={map} cfg={cfg} onUnit={onUnit} />
          <p className="map-legend" aria-hidden>
            <span className="map-legend__swatch map-legend__swatch--low" /> low reach
            <span className="map-legend__swatch map-legend__swatch--mid" />
            <span className="map-legend__swatch map-legend__swatch--high" /> high reach
          </p>
          <p className="muted">
            Colour is reachability, not a hazard. Incoming alerts are the table on the right. Compose draws a new area over a labelled village.
          </p>
        </div>
        <section className="panel table live-table" aria-label="Alerts">
          <div className="table__head" role="row">
            <span role="columnheader">ID</span>
            <span role="columnheader">Severity</span>
            <span role="columnheader">Headline</span>
            <span role="columnheader">Source</span>
            <span role="columnheader">Status</span>
            <span role="columnheader">Effective</span>
          </div>
          <div className="table__body table__body--virtual" ref={parentRef}>
            {loading && <p className="muted table__empty">Loading…</p>}
            {!loading && alerts.length === 0 && (
              <p className="muted table__empty">No alerts.</p>
            )}
            <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
              {virtualizer.getVirtualItems().map((item) => {
                const a = alerts[item.index];
                return (
                  <button
                    key={a.id}
                    className="table__row"
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${item.start}px)`,
                    }}
                    onClick={() => onOpen(a.id)}
                    role="row"
                  >
                    <span className="mono muted">{a.id}</span>
                    <SeverityBadge severity={a.severity} />
                    <span className="table__headline">{a.headline}</span>
                    <span className="mono muted table__source">
                      {a.source_id}
                      {a.is_authoritative && <ProvenanceChip kind="authoritative" />}
                    </span>
                    <span className={`status status--${a.lifecycle_status}`}>
                      {a.lifecycle_status}
                    </span>
                    <time className="mono muted" dateTime={a.effective_at}>
                      {relative(a.effective_at)}
                    </time>
                  </button>
                );
              })}
            </div>
          </div>
        </section>
        <aside className="panel live-feed" aria-label="Live delivery feed">
          <p className="screen__kicker">Delivery events</p>
          <h3>Live feed</h3>
          {feed.length === 0 && <p className="muted">Waiting for acknowledgements.</p>}
          <ol className="live-feed__list">
            {feed.map((item) => {
              const rowKey = `${item.delivery_id}-${item.event_type}-${item.occurred_at}`;
              return (
              <li key={rowKey}>
                <button className={`live-feed__row${rowKey === freshHead ? " is-new" : ""}`} onClick={() => onOpen(item.alert_id)}>
                  <time className="mono muted" dateTime={item.occurred_at}>
                    {relative(item.occurred_at)}
                  </time>
                  <span className="live-feed__verb">{feedLabel(item.event_type)}</span>
                  <span className="live-feed__head">{item.headline}</span>
                  <span className="mono muted">{item.channel_code}</span>
                </button>
              </li>
              );
            })}
          </ol>
        </aside>
      </div>
    </div>
  );
}
