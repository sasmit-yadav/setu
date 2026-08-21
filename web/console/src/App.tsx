import { useCallback, useEffect, useMemo, useState } from "react";
import { Command, HeartPulse, LogOut, Map, Radio, Siren } from "lucide-react";
import { endpoints, getToken, setToken, type Me } from "./lib/api";
import { CommandPalette, type Command as Cmd } from "./components/CommandPalette";
import { Login } from "./pages/Login";
import { LiveOps } from "./pages/LiveOps";
import { AlertDetail } from "./pages/AlertDetail";
import { AssistanceQueue } from "./pages/AssistanceQueue";
import { Composer } from "./pages/Composer";
import { IncidentPage } from "./pages/Incident";
import { CommandBoard } from "./pages/CommandBoard";
import { Methodology } from "./pages/Methodology";
import { Analytics } from "./pages/Analytics";
import { RelayTasks } from "./pages/RelayTasks";
import { Enrollment } from "./pages/Enrollment";
import { ReachabilityCard } from "./components/ReachabilityCard";

type View =
  | { name: "live" }
  | { name: "alert"; id: number }
  | { name: "queue" }
  | { name: "compose" }
  | { name: "incident"; id: number }
  | { name: "board" }
  | { name: "method" }
  | { name: "analytics" }
  | { name: "relay" }
  | { name: "enroll" }
  | { name: "unit"; id: number };

function roleChip(role: string): string {
  if (role === "auditor") return "chip chip--bootstrap";
  if (role === "relay_node") return "chip chip--human";
  if (role === "state_admin") return "chip chip--auto";
  return "chip chip--peer";
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const [view, setView] = useState<View>({ name: "live" });
  const [lastIncidentId, setLastIncidentId] = useState<number | null>(null);

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setChecked(true);
      return;
    }
    try {
      setMe(await endpoints.me());
    } catch {
      setToken(null);
      setMe(null);
    } finally {
      setChecked(true);
    }
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  function signOut() {
    setToken(null);
    setMe(null);
    setView({ name: "live" });
  }

  const openIncident = useCallback((id: number) => {
    setLastIncidentId(id);
    setView({ name: "incident", id });
  }, []);

  const commands: Cmd[] = useMemo(
    () => [
      { id: "live", label: "Go to Live Operations", hint: "map + table", shortcut: "G L", run: () => setView({ name: "live" }) },
      { id: "incident", label: "Go to Incident", hint: lastIncidentId ? "last opened" : "via board", shortcut: "G I", run: () => {
        if (lastIncidentId) openIncident(lastIncidentId);
        else setView({ name: "board" });
      } },
      { id: "compose", label: "Compose alert", hint: "draw polygon", shortcut: "G C", run: () => setView({ name: "compose" }) },
      { id: "queue", label: "Go to Assistance queue", hint: "open cases", shortcut: "G Q", run: () => setView({ name: "queue" }) },
      { id: "board", label: "Command Board", hint: "common operating picture", shortcut: "G B", run: () => setView({ name: "board" }) },
      { id: "method", label: "Methodology", hint: "thresholds and capability", shortcut: "G M", run: () => setView({ name: "method" }) },
      { id: "analytics", label: "Analytics", hint: "lead time + coverage", shortcut: "G A", run: () => setView({ name: "analytics" }) },
      { id: "relay", label: "Relay tasks", hint: "HUMAN confirm", run: () => setView({ name: "relay" }) },
      { id: "enroll", label: "CSV enrollment", hint: "dry-run then commit", run: () => setView({ name: "enroll" }) },
      { id: "signout", label: "Sign out", hint: me?.email, run: signOut },
    ],
    [me, lastIncidentId, openIncident],
  );

  if (!checked) return null;
  if (!me) return <Login onAuthed={() => void loadMe()} />;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__mark" aria-hidden />
          <Radio size={16} aria-hidden />
          <strong>SETU</strong>
          <span className="muted">Ops</span>
        </div>

        <nav className="topbar__nav" aria-label="Primary">
          <button
            className={`navlink ${view.name === "live" || view.name === "alert" || view.name === "compose" ? "is-active" : ""}`}
            onClick={() => setView({ name: "live" })}
          >
            Live Operations
          </button>
          <button
            className={`navlink ${view.name === "incident" ? "is-active" : ""}`}
            onClick={() => {
              if (lastIncidentId) openIncident(lastIncidentId);
              else setView({ name: "board" });
            }}
          >
            <Siren size={12} aria-hidden /> Incident
          </button>
          <button className={`navlink ${view.name === "queue" ? "is-active" : ""}`} onClick={() => setView({ name: "queue" })}>
            <HeartPulse size={12} aria-hidden /> Assistance
          </button>
          <button className={`navlink ${view.name === "board" ? "is-active" : ""}`} onClick={() => setView({ name: "board" })}>
            <Map size={12} aria-hidden /> Board
          </button>
          <button className={`navlink ${view.name === "method" ? "is-active" : ""}`} onClick={() => setView({ name: "method" })}>
            Methodology
          </button>
          <button className={`navlink ${view.name === "analytics" ? "is-active" : ""}`} onClick={() => setView({ name: "analytics" })}>
            Analytics
          </button>
          <button className={`navlink ${view.name === "relay" ? "is-active" : ""}`} onClick={() => setView({ name: "relay" })}>
            Relay
          </button>
          <button className={`navlink ${view.name === "enroll" ? "is-active" : ""}`} onClick={() => setView({ name: "enroll" })}>
            Enrollment
          </button>
        </nav>

        <div className="topbar__right">
          <span className="topbar__hint muted">
            <Command size={12} aria-hidden /> <kbd className="mono">Ctrl K</kbd>
          </span>
          <span className="topbar__user mono">{me.email}</span>
          <span className={roleChip(me.role)}>{me.role.replace("_", " ")}</span>
          <button className="btn btn--ghost" onClick={signOut} aria-label="Sign out">
            <LogOut size={14} aria-hidden />
          </button>
        </div>
      </header>

      <main className="shell__body">
        {view.name === "live" && (
          <LiveOps
            onOpen={(id) => setView({ name: "alert", id })}
            onCompose={() => setView({ name: "compose" })}
            onUnit={(id) => setView({ name: "unit", id })}
          />
        )}
        {view.name === "alert" && (
          <AlertDetail
            id={view.id}
            onBack={() => setView({ name: "live" })}
            onIncident={openIncident}
            onOpen={(alertId) => setView({ name: "alert", id: alertId })}
          />
        )}
        {view.name === "queue" && <AssistanceQueue />}
        {view.name === "compose" && (
          <Composer
            onBack={() => setView({ name: "live" })}
            onOpen={(id) => setView({ name: "alert", id })}
          />
        )}
        {view.name === "incident" && (
          <IncidentPage
            id={view.id}
            onBack={() => setView({ name: "board" })}
            onAlert={(alertId) => setView({ name: "alert", id: alertId })}
            canClose={me.role === "state_admin"}
          />
        )}
        {view.name === "board" && (
          <CommandBoard onIncident={openIncident} />
        )}
        {view.name === "method" && <Methodology />}
        {view.name === "analytics" && <Analytics />}
        {view.name === "relay" && <RelayTasks />}
        {view.name === "enroll" && <Enrollment />}
        {view.name === "unit" && (
          <ReachabilityCard unitId={view.id} onBack={() => setView({ name: "live" })} />
        )}
      </main>

      <CommandPalette commands={commands} />
    </div>
  );
}
