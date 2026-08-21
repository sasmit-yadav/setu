import { useCallback, useEffect, useMemo, useState } from "react";
import { Command, HeartPulse, LogOut, Map, Radio, Siren } from "lucide-react";
import { endpoints, getToken, setToken, type Me } from "./lib/api";
import { lookup, useT } from "./lib/i18n";
import { CommandPalette, type Command as Cmd } from "./components/CommandPalette";
import { LangSwitcher } from "./components/LangSwitcher";
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
  const { t } = useT();
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

  const writeRoles = me?.role === "officer" || me?.role === "state_admin";
  const relayRoles = writeRoles || me?.role === "relay_node";

  const commands: Cmd[] = useMemo(
    () => {
      const all: Cmd[] = [
        { id: "live", label: t("cmd.map"), hint: t("cmd.mapHint"), shortcut: "G L", run: () => setView({ name: "live" }) },
        { id: "incident", label: t("cmd.emergency"), hint: t("cmd.emergencyHint"), shortcut: "G I", run: () => {
          if (lastIncidentId) openIncident(lastIncidentId);
          else setView({ name: "board" });
        } },
      ];
      if (writeRoles) {
        all.push({ id: "compose", label: t("cmd.write"), hint: t("cmd.writeHint"), shortcut: "G C", run: () => setView({ name: "compose" }) });
        all.push({ id: "queue", label: t("cmd.help"), hint: t("cmd.helpHint"), shortcut: "G Q", run: () => setView({ name: "queue" }) });
      }
      all.push({ id: "board", label: t("cmd.overview"), hint: t("cmd.overviewHint"), shortcut: "G B", run: () => setView({ name: "board" }) });
      all.push({ id: "method", label: t("cmd.measure"), shortcut: "G M", run: () => setView({ name: "method" }) });
      all.push({ id: "analytics", label: t("cmd.timing"), shortcut: "G A", run: () => setView({ name: "analytics" }) });
      if (relayRoles) {
        all.push({ id: "relay", label: t("cmd.foot"), hint: t("cmd.footHint"), run: () => setView({ name: "relay" }) });
      }
      if (writeRoles) {
        all.push({ id: "enroll", label: t("cmd.register"), hint: t("cmd.registerHint"), run: () => setView({ name: "enroll" }) });
      }
      all.push({ id: "signout", label: t("app.signOut"), hint: me?.email, run: signOut });
      return all;
    },
    [t, me, lastIncidentId, openIncident, writeRoles, relayRoles],
  );

  if (!checked) return null;
  if (!me) return <Login onAuthed={() => void loadMe()} />;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__mark" aria-hidden />
          <Radio size={16} aria-hidden />
          <strong>{t("app.name")}</strong>
          <span className="muted">{t("app.desk")}</span>
        </div>

        <nav className="topbar__nav" aria-label="Primary">
          <button
            className={`navlink ${view.name === "live" || view.name === "alert" || view.name === "compose" ? "is-active" : ""}`}
            onClick={() => setView({ name: "live" })}
          >
            {t("nav.map")}
          </button>
          <button
            className={`navlink ${view.name === "incident" ? "is-active" : ""}`}
            onClick={() => {
              if (lastIncidentId) openIncident(lastIncidentId);
              else setView({ name: "board" });
            }}
          >
            <Siren size={12} aria-hidden /> {t("nav.emergency")}
          </button>
          {writeRoles && (
          <button className={`navlink ${view.name === "queue" ? "is-active" : ""}`} onClick={() => setView({ name: "queue" })}>
            <HeartPulse size={12} aria-hidden /> {t("nav.help")}
          </button>
          )}
          <button className={`navlink ${view.name === "board" ? "is-active" : ""}`} onClick={() => setView({ name: "board" })}>
            <Map size={12} aria-hidden /> {t("nav.overview")}
          </button>
          <button className={`navlink ${view.name === "method" ? "is-active" : ""}`} onClick={() => setView({ name: "method" })}>
            {t("nav.measure")}
          </button>
          <button className={`navlink ${view.name === "analytics" ? "is-active" : ""}`} onClick={() => setView({ name: "analytics" })}>
            {t("nav.timing")}
          </button>
          {relayRoles && (
          <button className={`navlink ${view.name === "relay" ? "is-active" : ""}`} onClick={() => setView({ name: "relay" })}>
            {t("nav.foot")}
          </button>
          )}
          {writeRoles && (
          <button className={`navlink ${view.name === "enroll" ? "is-active" : ""}`} onClick={() => setView({ name: "enroll" })}>
            {t("nav.register")}
          </button>
          )}
        </nav>

        <div className="topbar__right">
          <LangSwitcher />
          <span className="topbar__hint muted">
            <Command size={12} aria-hidden /> <kbd className="mono">Ctrl K</kbd>
          </span>
          <span className="topbar__user mono">{me.email}</span>
          <span className={roleChip(me.role)}>{lookup(t, "role", me.role)}</span>
          <button className="btn btn--ghost" onClick={signOut} aria-label={t("app.signOut")}>
            <LogOut size={14} aria-hidden />
          </button>
        </div>
      </header>

      <main className="shell__body">
        {view.name === "live" && (
          <LiveOps
            onOpen={(id) => setView({ name: "alert", id })}
            onCompose={writeRoles ? () => setView({ name: "compose" }) : undefined}
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

      <CommandPalette commands={commands} emptyLabel={t("cmd.none")} searchLabel={t("app.search")} />
    </div>
  );
}
