import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { endpoints, type AssistanceCase, type PublicConfig } from "../lib/api";
import { lookup, useT } from "../lib/i18n";
import { Kpi } from "../components/Kpi";
import { useOpsSocket } from "../lib/useOpsSocket";

function csv(cfg: PublicConfig | null, key: string): string[] {
  const value = cfg?.[key];
  if (typeof value !== "string" || !value.trim()) return [];
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

function typeLabel(cfg: PublicConfig | null, id: string): string {
  const value = cfg?.[`response.label.${id}`];
  return typeof value === "string" && value.trim() ? value : id;
}

function nextStatus(sequence: string[], current: string): string | null {
  const index = sequence.indexOf(current);
  if (index < 0 || index >= sequence.length - 1) return null;
  return sequence[index + 1];
}

function factorWidth(value: number): string {
  const clamped = Math.min(Math.max(value, 0), 1);
  return `${Math.round(clamped * 100)}%`;
}

export function AssistanceQueue() {
  const { t } = useT();
  const [rows, setRows] = useState<AssistanceCase[]>([]);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [team, setTeam] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [nextRows, nextCfg] = await Promise.all([
        endpoints.assistance("all"),
        endpoints.publicConfig(),
      ]);
      setRows(nextRows);
      setCfg(nextCfg);
      setError(null);
    } catch {
      setError(t("queue.loadError"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);
  useOpsSocket(() => void load());

  const sequence = csv(cfg, "assistance.status_sequence");

  async function assign(id: number) {
    setBusyId(id);
    try {
      await endpoints.assignCase(id, team.trim());
      await load();
    } catch {
      setError(t("queue.assignFail"));
    } finally {
      setBusyId(null);
    }
  }

  async function advance(row: AssistanceCase) {
    const next = nextStatus(sequence, row.status);
    if (!next) return;
    setBusyId(row.id);
    try {
      await endpoints.patchCase(row.id, {
        status: next,
        assigned_team: row.assigned_team ?? team.trim(),
      });
      await load();
    } catch {
      setError(t("queue.statusFail"));
    } finally {
      setBusyId(null);
    }
  }

  const urgentId = csv(cfg, "response.help_types")[0];
  const urgentCount = urgentId
    ? rows.filter((r) => r.response_type === urgentId).length
    : 0;
  const openCount = rows.filter((r) => r.status !== "closed").length;

  return (
    <div className="screen">
      <header className="screen__head">
        <div>
          <p className="screen__kicker">{t("queue.kicker")}</p>
          <h2>{t("queue.title")}</h2>
        </div>
        <label className="field queue__team">
          <span>{t("queue.team")}</span>
          <input
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            placeholder={t("queue.teamPh")}
          />
        </label>
        <button className="btn btn--ghost" onClick={() => void load()} aria-label={t("live.refresh")}>
          <RefreshCw size={14} aria-hidden /> {t("live.refresh")}
        </button>
      </header>

      <section className="kpis" aria-label={t("queue.open")}>
        <Kpi label={t("queue.open")} value={openCount} tone={openCount ? "warn" : "ok"} />
        {urgentId ? (
          <Kpi
            label={typeLabel(cfg, urgentId)}
            value={urgentCount}
            tone={urgentCount ? "danger" : undefined}
          />
        ) : null}
      </section>

      {error && <p className="danger" role="alert">{error}</p>}

      <section className="panel table queue" aria-label={t("queue.casesAria")} role="table">
        <div className="table__head queue__head" role="row">
          <span role="columnheader">{t("queue.colPriority")}</span>
          <span role="columnheader">{t("queue.colNeed")}</span>
          <span role="columnheader">{t("queue.colUnit")}</span>
          <span role="columnheader">{t("queue.colStatus")}</span>
          <span role="columnheader">{t("queue.colActions")}</span>
        </div>
        <div className="table__body">
          {loading && <p className="muted table__empty">{t("common.loading")}</p>}
          {!loading && rows.length === 0 && (
            <p className="muted table__empty">{t("queue.empty")}</p>
          )}
          {rows.map((row, index) => {
            const next = nextStatus(sequence, row.status);
            const factors = row.priority_factors as {
              factors?: Record<string, number>;
              weights?: Record<string, number>;
              formula?: string;
            };
            const first = index === 0;
            return (
              <div key={row.id}>
                <div className={`table__row queue__row${first ? " is-first" : ""}`} role="row">
                  <button
                    className="mono kpi__value queue__score"
                    onClick={() => setOpenId(openId === row.id ? null : row.id)}
                    aria-expanded={openId === row.id}
                  >
                    {row.priority_score.toFixed(2)}
                  </button>
                  <span>
                    {typeLabel(cfg, row.response_type)}
                    {row.free_text ? <span className="muted"> — {row.free_text}</span> : null}
                  </span>
                  <span>{row.unit_name}</span>
                  <span className={`status-chip status-chip--${row.status}`}>
                    {lookup(t, "case", row.status)}
                  </span>
                  {row.status === "new" ? (
                    <button
                      className="btn btn--approve"
                      disabled={busyId === row.id || !team.trim()}
                      onClick={() => void assign(row.id)}
                    >
                      {busyId === row.id ? t("queue.assigning") : t("queue.assign")}
                    </button>
                  ) : next ? (
                    <button
                      className="btn"
                      disabled={busyId === row.id}
                      onClick={() => void advance(row)}
                    >
                      {lookup(t, "case", next)}
                    </button>
                  ) : null}
                </div>
                {openId === row.id && (
                  <div className="queue__factors">
                    <p>{first ? t("queue.whyFirst") : t("queue.whyRank")}</p>
                    {factors.formula && <p className="mono muted">{factors.formula}</p>}
                    {factors.factors &&
                      Object.entries(factors.factors).map(([key, value]) => (
                        <div key={key} className="queue__factor">
                          <span>
                            {lookup(t, "factor", key)}: {value} × {factors.weights?.[key] ?? "?"}
                          </span>
                          <span className="queue__bar" aria-hidden>
                            <span style={{ width: factorWidth(Number(value)) }} />
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
