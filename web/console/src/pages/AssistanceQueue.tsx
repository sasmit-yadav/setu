import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { endpoints, type AssistanceCase, type PublicConfig } from "../lib/api";
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
      setError("Could not load the assistance queue.");
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
      setError("Assignment failed.");
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
      setError("Status update failed.");
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
          <p className="screen__kicker">Response</p>
          <h2>Assistance queue</h2>
        </div>
        <label className="field queue__team">
          <span>Assign to team</span>
          <input
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            placeholder="Team name"
          />
        </label>
        <button className="btn btn--ghost" onClick={() => void load()} aria-label="Refresh">
          <RefreshCw size={14} aria-hidden /> Refresh
        </button>
      </header>

      <section className="kpis" aria-label="Queue summary">
        <Kpi label="Open cases" value={openCount} tone={openCount ? "warn" : "ok"} />
        {urgentId ? (
          <Kpi
            label={typeLabel(cfg, urgentId)}
            value={urgentCount}
            tone={urgentCount ? "danger" : undefined}
          />
        ) : null}
      </section>

      {error && <p className="danger" role="alert">{error}</p>}

      <section className="panel table queue" aria-label="Cases" role="table">
        <div className="table__head queue__head" role="row">
          <span role="columnheader">Priority</span>
          <span role="columnheader">Need</span>
          <span role="columnheader">Unit</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Actions</span>
        </div>
        <div className="table__body">
          {loading && <p className="muted table__empty">Loading…</p>}
          {!loading && rows.length === 0 && (
            <p className="muted table__empty">No open cases.</p>
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
                  <span className={`status-chip status-chip--${row.status}`}>{row.status}</span>
                  {row.status === "new" ? (
                    <button
                      className="btn btn--approve"
                      disabled={busyId === row.id || !team.trim()}
                      onClick={() => void assign(row.id)}
                    >
                      {busyId === row.id ? "Assigning…" : `Assign ${typeLabel(cfg, row.response_type)}`}
                    </button>
                  ) : next ? (
                    <button
                      className="btn"
                      disabled={busyId === row.id}
                      onClick={() => void advance(row)}
                    >
                      {next}
                    </button>
                  ) : null}
                </div>
                {openId === row.id && (
                  <div className="queue__factors">
                    <p>{first ? "Why is this first" : "Why this rank"}</p>
                    {factors.formula && <p className="mono muted">{factors.formula}</p>}
                    {factors.factors &&
                      Object.entries(factors.factors).map(([key, value]) => (
                        <div key={key} className="queue__factor">
                          <span className="mono">
                            {key}: {value} × {factors.weights?.[key] ?? "?"}
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
