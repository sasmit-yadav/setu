import { useMemo, useState } from "react";
import type { CitizenReply, PublicConfig } from "../lib/api";
import { useT } from "../lib/i18n";
import { Kpi } from "./Kpi";
import { SeverityBadge } from "./SeverityBadge";
import {
  filterReplies,
  isHelpReply,
  saidLabel,
  tallyReplies,
  viaLabel,
  type ReplyFilter,
} from "../lib/replies";

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

const FILTERS: { id: ReplyFilter; label: string }[] = [
  { id: "all", label: "reply.filterAll" },
  { id: "sms", label: "reply.via.sms" },
  { id: "ivr", label: "reply.via.ivr" },
  { id: "fcm", label: "reply.via.fcm" },
  { id: "safe", label: "reply.filterSafe" },
  { id: "help", label: "reply.filterHelp" },
];

export function ReplyInbox({
  rows,
  cfg,
  showWarning = false,
  onOpen,
}: {
  rows: CitizenReply[];
  cfg: PublicConfig | null;
  showWarning?: boolean;
  onOpen?: (alertId: number) => void;
}) {
  const { t } = useT();
  const [filter, setFilter] = useState<ReplyFilter>("all");
  const counts = useMemo(() => tallyReplies(rows, cfg), [rows, cfg]);
  const visible = useMemo(() => filterReplies(rows, filter, cfg), [rows, filter, cfg]);

  return (
    <section className={`panel table reply-inbox${showWarning ? " reply-inbox--alert" : ""}`} aria-label={t("alert.replies")}>
      <div className="reply-inbox__intro">
        <p className="screen__kicker">{t("live.repliesKicker")}</p>
        <h3>{t("alert.replies")}</h3>
        <p className="lede">{t("alert.repliesHint")}</p>
      </div>

      <section className="kpis" aria-label={t("alert.replies")}>
        <Kpi label={t("reply.kpiTotal")} value={counts.total} tone={counts.total ? "info" : undefined} />
        <Kpi label={t("reply.kpiSafe")} value={counts.safe} tone={counts.safe ? "ok" : undefined} />
        <Kpi
          label={t("reply.kpiHelp")}
          value={counts.help}
          tone={counts.help ? "danger" : "ok"}
        />
        <Kpi label={t("reply.kpiSms")} value={counts.sms} />
        <Kpi label={t("reply.kpiIvr")} value={counts.ivr} />
        <Kpi label={t("reply.kpiApp")} value={counts.app} />
      </section>

      <div className="chip-row" role="toolbar" aria-label={t("reply.filterAll")}>
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`chip${filter === item.id ? " chip--auto" : ""}`}
            aria-pressed={filter === item.id}
            onClick={() => setFilter(item.id)}
          >
            {t(item.label)}
          </button>
        ))}
      </div>

      <div className="table__head" role="row">
        <span role="columnheader">{t("reply.colWhen")}</span>
        {showWarning ? <span role="columnheader">{t("live.colSeverity")}</span> : null}
        <span role="columnheader">{t("reply.colVia")}</span>
        <span role="columnheader">{t("reply.colSaid")}</span>
        <span role="columnheader">{t("reply.colVillage")}</span>
        {showWarning ? <span role="columnheader">{t("reply.colWarning")}</span> : null}
      </div>
      <div className="table__body">
        {visible.length === 0 && (
          <p className="muted table__empty">{t("alert.repliesEmpty")}</p>
        )}
        {visible.map((row) => {
          const help = isHelpReply(row.response_type, cfg);
          const openable = showWarning && onOpen && row.alert_id != null;
          const inner = (
            <>
              <time className="mono muted" dateTime={row.received_at}>
                {relative(row.received_at)}
              </time>
              {showWarning && row.severity ? <SeverityBadge severity={row.severity} /> : null}
              <span>{viaLabel(t, row.channel_code)}</span>
              <span>
                <span className={`status-chip ${help ? "status-chip--help" : "status-chip--assisted"}`}>
                  {help ? t("reply.filterHelp") : t("reply.filterSafe")}
                </span>
                {" "}
                {saidLabel(cfg, row.response_type, row.free_text)}
              </span>
              <span>{row.unit_name}</span>
              {showWarning ? (
                <span className="table__headline" title={row.headline ?? undefined}>
                  {row.headline}
                </span>
              ) : null}
            </>
          );
          return openable ? (
            <button
              key={row.id}
              type="button"
              className="table__row"
              role="row"
              onClick={() => onOpen(row.alert_id!)}
            >
              {inner}
            </button>
          ) : (
            <div key={row.id} className="table__row" role="row">
              {inner}
            </div>
          );
        })}
      </div>
    </section>
  );
}
