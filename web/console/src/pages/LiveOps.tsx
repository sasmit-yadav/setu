import { useCallback, useEffect, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { PenLine, RefreshCw } from "lucide-react";
import {
  endpoints,
  type AlertSummary,
  type CitizenReply,
  type MapPayload,
  type OpsFeedItem,
  type OpsSummary,
  type PublicConfig,
} from "../lib/api";
import { lookup, useT } from "../lib/i18n";
import { SeverityBadge } from "../components/SeverityBadge";
import { Kpi } from "../components/Kpi";
import { LiveMap } from "../components/LiveMap";
import { ReplyInbox } from "../components/ReplyInbox";
import { useOpsSocket } from "../lib/useOpsSocket";
import { saidLabel, viaLabel } from "../lib/replies";

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

export function LiveOps({
  onOpen,
  onCompose,
  onUnit,
}: {
  onOpen: (id: number) => void;
  onCompose?: () => void;
  onUnit: (id: number) => void;
}) {
  const { t } = useT();
  const [alerts, setAlerts] = useState<AlertSummary[]>([]);
  const [official, setOfficial] = useState<AlertSummary[]>([]);
  const [map, setMap] = useState<MapPayload | null>(null);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [feed, setFeed] = useState<OpsFeedItem[]>([]);
  const [replies, setReplies] = useState<CitizenReply[]>([]);
  // The feeds poll worldwide, but an officer's job is their own district.
  // India is the default view; "Everywhere" is one tap away, never the
  // thing you have to wade through first.
  const [scope, setScope] = useState<"india" | "world">("india");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const parentRef = useRef<HTMLDivElement>(null);
  const feedHeadRef = useRef<string | null>(null);
  const [freshHead, setFreshHead] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [nextAlerts, usgsDrafts, gdacsDrafts, nextMap, nextCfg, nextSummary, nextFeed, nextReplies] = await Promise.all([
        endpoints.alerts(),
        endpoints.alerts({ source_id: "usgs", lifecycle_status: "draft", limit: 40 }),
        endpoints.alerts({ source_id: "gdacs", lifecycle_status: "draft", limit: 40 }),
        endpoints.map(),
        endpoints.publicConfig(),
        endpoints.opsSummary(),
        endpoints.opsFeed(),
        endpoints.opsReplies().catch(() => [] as CitizenReply[]),
      ]);
      const pinned = [...usgsDrafts, ...gdacsDrafts].filter(
        (row) => row.source_id === "usgs" || row.source_id === "gdacs",
      );
      const seen = new Set(pinned.map((row) => row.id));
      setOfficial(pinned);
      setAlerts([...pinned, ...nextAlerts.filter((row) => !seen.has(row.id))]);
      setMap(nextMap);
      setCfg(nextCfg);
      setSummary(nextSummary);
      setFeed(nextFeed);
      setReplies(nextReplies);
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
      setError(t("live.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);
  const link = useOpsSocket(() => void load());
  const liveAlerts = alerts.filter((a) => a.lifecycle_status === "active");

  const tileSource = String(cfg?.["map.tile_source"] ?? map?.tile_source ?? "");

  // A cancelled or superseded alert is not a live warning. They were filling
  // this table with rows whose "when" was in the future and whose status was
  // Cancelled; history belongs on the incident timeline, not here.
  const current = alerts.filter(
    (a) => a.lifecycle_status !== "cancelled" && a.lifecycle_status !== "superseded",
  );
  const inScope = (a: AlertSummary) => scope === "world" || a.domestic;
  const visibleAlerts = current.filter(inScope);
  const visibleOfficial = official.filter(inScope);

  // Counted over the official external feeds only. Our own nowcast and an
  // officer's own draft are not "what the feeds are reporting".
  const feedRows = current.filter((a) => a.source_id === "usgs" || a.source_id === "gdacs");
  const feedDomestic = feedRows.filter((a) => a.domestic).length;
  const feedForeign = feedRows.length - feedDomestic;
  // Our own nowcast is why "0 in India" from the official feeds can sit above a
  // table showing 23 Indian rows. Both are true; the desk has to say which is
  // which or the two numbers look like a contradiction.
  const nowcastDomestic = current.filter(
    (a) => a.source_id === "thunderstorm_nowcast" && a.domestic,
  ).length;
  const nowcastVisible = visibleAlerts.filter(
    (a) => a.source_id === "thunderstorm_nowcast",
  ).length;

  const virtualizer = useVirtualizer({
    count: visibleAlerts.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 56,
    overscan: 12,
  });


  return (
    <div className="screen screen--wide">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("live.kicker")}</p>
          <h2>{t("live.title")}</h2>
        </div>
        {onCompose && (
        <button type="button" className="btn btn--primary" onClick={onCompose}>
          <PenLine size={14} aria-hidden /> {t("live.write")}
        </button>
        )}
        <button type="button" className="btn btn--ghost" onClick={() => void load()} aria-label={t("live.refresh")}>
          <RefreshCw size={14} aria-hidden /> {t("live.refresh")}
        </button>
        <p className={`link-chip link-chip--${link}`} role="status" aria-label={t("live.link")}>
          <span className="link-chip__dot" aria-hidden />
          {link === "live" ? t("app.live") : link === "connecting" ? t("app.connecting") : t("app.offline")}
        </p>
      </header>

      <div className="trouble" aria-label={t("live.trouble")}>
        <span className="trouble__label muted">{t("live.trouble")}</span>
        {liveAlerts.length === 0 ? (
          <p className="muted live-empty">{t("live.noLive")}</p>
        ) : (
          liveAlerts.map((a) => (
            <button
              key={a.id}
              type="button"
              className={`trouble__tick trouble__tick--${a.severity}`}
              onClick={() => onOpen(a.id)}
              title={a.headline}
            >
              <SeverityBadge severity={a.severity} />
              <span className="sr-only">{a.headline}</span>
            </button>
          ))
        )}
      </div>

      {official.length > 0 ? (
      <section className="inbox panel" aria-label={t("live.officialTitle")}>
        <p className="screen__kicker">{t("live.officialTitle")}</p>
        <p className="lede">{t("live.officialHint")}</p>
        <div className="scope" role="group" aria-label={t("live.scopeLabel")}>
          <button
            type="button"
            className={`chip chip--toggle${scope === "india" ? " is-on" : ""}`}
            aria-pressed={scope === "india"}
            onClick={() => setScope("india")}
          >
            {t("live.scopeIndia")} <span className="mono">{feedDomestic}</span>
          </button>
          <button
            type="button"
            className={`chip chip--toggle${scope === "world" ? " is-on" : ""}`}
            aria-pressed={scope === "world"}
            onClick={() => setScope("world")}
          >
            {t("live.scopeWorld")} <span className="mono">{feedRows.length}</span>
          </button>
        </div>
        <p className="scope__tally muted" role="status">
          {feedDomestic === 0
            ? t("live.tallyNoneInIndia", { foreign: feedForeign })
            : scope === "india"
              ? t("live.tallyIndiaOnly", { domestic: feedDomestic, foreign: feedForeign })
              : t("live.tallyWorld", { total: feedRows.length, domestic: feedDomestic })}
        </p>
        {nowcastDomestic > 0 && (
          <p className="scope__tally muted">
            {t("live.tallyOwnNowcast", { n: nowcastDomestic })}
          </p>
        )}
        <ul className="inbox__list">
          {visibleOfficial.map((row) => (
            <li key={row.id}>
              <button type="button" className="inbox__row" onClick={() => onOpen(row.id)}>
                <SeverityBadge severity={row.severity} />
                <span className="inbox__head">{row.headline}</span>
                <span className="muted">{row.source_id}</span>
                <span className={`status status--${row.lifecycle_status}`}>
                  {lookup(t, "life", row.lifecycle_status)}
                </span>
                <span className="inbox__go">{t("live.officialOpen")}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      ) : null}

      {summary && (
        <section className="kpis" aria-label={t("live.kpis")}>
          <Kpi label={t("live.kpiTargeted")} value={summary.targeted} />
          <Kpi
            label={t("live.kpiDelivered")}
            value={summary.delivered}
            tone="info"
            note={summary.delivered_note}
          />
          <Kpi
            label={t("live.kpiAcked")}
            value={summary.acknowledged}
            tone={summary.acknowledged ? "ok" : undefined}
            note={summary.acknowledged_note}
          />
          <Kpi
            label={t("live.kpiRisk")}
            value={summary.at_risk}
            tone={summary.at_risk ? "danger" : "ok"}
            note={summary.at_risk_note}
          />
        </section>
      )}

      <ReplyInbox rows={replies} cfg={cfg} showWarning onOpen={onOpen} />

      {tileSource !== "pmtiles_local" && (
        <p className="muted" role="status">
          {t("live.basemapNote")}
        </p>
      )}
      {error && <p className="danger" role="alert">{error}</p>}

      <div className="live-split">
        <div className="live-map-wrap">
          <LiveMap payload={map} cfg={cfg} onUnit={onUnit} />
          <p className="map-legend" aria-label={t("live.legend")}>
            <span className="map-legend__swatch map-legend__swatch--low" /> {t("live.legendLow")}
            <span className="map-legend__swatch map-legend__swatch--mid" />
            <span className="map-legend__swatch map-legend__swatch--high" /> {t("live.legendHigh")}
          </p>
          <p className="lede">{t("live.mapHint")}</p>
        </div>
        <section className="panel table live-table" aria-label={t("live.table")} role="table">
          <div className="table__head" role="row">
            <span role="columnheader">{t("live.colSeverity")}</span>
            <span role="columnheader">{t("live.colHeadline")}</span>
            <span role="columnheader">{t("live.colSource")}</span>
            <span role="columnheader">{t("live.colStatus")}</span>
            <span role="columnheader">{t("live.colWhen")}</span>
          </div>
          <div className="table__body table__body--virtual" ref={parentRef}>
            {loading && <p className="muted table__empty">{t("live.loading")}</p>}
            {!loading && visibleAlerts.length === 0 && (
              <p className="muted table__empty">{t("live.empty")}</p>
            )}
            <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
              {virtualizer.getVirtualItems().map((item) => {
                const a = visibleAlerts[item.index];
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
                    type="button"
                  >
                    <SeverityBadge severity={a.severity} />
                    <span className="table__headline">{a.headline}</span>
                    <span className="muted table__source">{a.source_id}</span>
                    <span className={`status status--${a.lifecycle_status}`}>
                      {lookup(t, "life", a.lifecycle_status)}
                    </span>
                    <time className="mono muted" dateTime={a.effective_at}>
                      {relative(a.effective_at)}
                    </time>
                  </button>
                );
              })}
            </div>
          </div>
          {/* A worldwide feed with nothing in India reads as "nothing is
            * happening" unless the domestic count is stated. The flag is a
            * real ST_Intersects against admin_unit, not a bounding box. */}
          {!loading && visibleAlerts.length > 0 && (
            <p className="table__tally muted">
              {t("live.tallyShowing", {
                shown: visibleAlerts.length,
                scope: scope === "india" ? t("live.scopeIndia") : t("live.scopeWorld"),
              })}
              {nowcastVisible > 0
                ? " " + t("live.tallyNowcastPart", {
                    warnings: visibleAlerts.length - nowcastVisible,
                    nowcast: nowcastVisible,
                  })
                : ""}
            </p>
          )}
        </section>
        <aside className="panel live-feed" aria-label={t("live.feedTitle")}>
          <p className="screen__kicker">{t("live.feedKicker")}</p>
          <h3>{t("live.feedTitle")}</h3>
          {feed.length === 0 && <p className="muted">{t("live.feedEmpty")}</p>}
          <ol className="live-feed__list">
            {feed.map((item) => {
              const rowKey = `${item.delivery_id}-${item.event_type}-${item.occurred_at}`;
              return (
              <li key={rowKey}>
                <button className={`live-feed__row${rowKey === freshHead ? " is-new" : ""}`} onClick={() => onOpen(item.alert_id)}>
                  <time className="mono muted" dateTime={item.occurred_at}>
                    {relative(item.occurred_at)}
                  </time>
                  <span className="live-feed__body">
                    <span className="live-feed__verb">{lookup(t, "feed", item.event_type)}</span>
                    <span className="live-feed__head" title={item.headline}>{item.headline}</span>
                    <span className="live-feed__meta muted">
                      {viaLabel(t, item.channel_code)}
                      {item.event_type === "citizen_response" && item.response_type
                        ? ` · ${saidLabel(cfg, item.response_type, item.free_text)}`
                        : ""}
                    </span>
                  </span>
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
