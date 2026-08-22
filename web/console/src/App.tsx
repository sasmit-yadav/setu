import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BookOpen,
  Clock,
  Footprints,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  Map,
  Menu,
  PanelLeftClose,
  PenLine,
  Radio,
  Siren,
  UserPlus,
} from "lucide-react";
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

const SIDEBAR_KEY = "setu.console.sidebar";

function readSidebarOpen(): boolean {
  try {
    const raw = localStorage.getItem(SIDEBAR_KEY);
    if (raw === "closed") return false;
  } catch {
    /* ignore */
  }
  return true;
}

function NavBtn({
  active,
  collapsed,
  icon,
  label,
  hint,
  onClick,
}: {
  active: boolean;
  collapsed: boolean;
  icon: ReactNode;
  label: string;
  hint?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`navlink sidebar__link ${active ? "is-active" : ""}`}
      aria-current={active ? "page" : undefined}
      title={collapsed ? (hint ? `${label} — ${hint}` : label) : undefined}
      onClick={onClick}
    >
      <span className="sidebar__icon" aria-hidden>
        {icon}
      </span>
      <span className="sidebar__text">
        <span>{label}</span>
        {hint ? <span className="muted sidebar__hint">{hint}</span> : null}
      </span>
    </button>
  );
}

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
  const [navOpen, setNavOpen] = useState(readSidebarOpen);

  function toggleNav() {
    setNavOpen((open) => {
      const next = !open;
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? "open" : "closed");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

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
        all.push({ id: "relay", label: t("cmd.foot"), hint: t("cmd.footHint"), shortcut: "G F", run: () => setView({ name: "relay" }) });
      }
      if (writeRoles) {
        all.push({ id: "enroll", label: t("cmd.register"), hint: t("cmd.registerHint"), run: () => setView({ name: "enroll" }) });
      }
      all.push({ id: "signout", label: t("app.signOut"), hint: me?.email, run: signOut });
      return all;
    },
    [t, me, lastIncidentId, openIncident, writeRoles, relayRoles],
  );

  useEffect(() => {
    const titles: Record<View["name"], string> = {
      live: t("live.title"),
      alert: t("live.title"),
      compose: t("compose.title"),
      queue: t("nav.help"),
      incident: t("nav.emergency"),
      board: t("nav.overview"),
      method: t("nav.measure"),
      analytics: t("nav.timing"),
      relay: t("nav.foot"),
      enroll: t("nav.register"),
      unit: t("unit.kicker"),
    };
    document.title = `${titles[view.name]} — SETU`;
  }, [t, view.name]);

  useEffect(() => {
    let pending = false;
    let timer = 0;
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return;
      const k = e.key.toLowerCase();
      if (!pending && k === "g") {
        e.preventDefault();
        pending = true;
        timer = window.setTimeout(() => {
          pending = false;
        }, 800);
        return;
      }
      if (pending) {
        pending = false;
        window.clearTimeout(timer);
        const cmd = commands.find((c) => c.shortcut?.toLowerCase() === `g ${k}`);
        if (cmd) {
          e.preventDefault();
          cmd.run();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(timer);
    };
  }, [commands]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape" || !navOpen) return;
      const el = e.target as HTMLElement | null;
      if (el?.tagName === "INPUT" || el?.tagName === "TEXTAREA") return;
      if (window.matchMedia("(max-width: 1100px)").matches) toggleNav();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  if (!checked) return null;
  if (!me) return <Login onAuthed={() => void loadMe()} />;

  return (
    <div className={`shell${navOpen ? "" : " shell--nav-collapsed"}`}>
      <a className="skip-link" href="#desk">
        {t("app.skip")}
      </a>
      <header className="topbar">
        <button
          type="button"
          className="btn btn--ghost topbar__menu"
          aria-expanded={navOpen}
          aria-controls="desk-nav"
          onClick={toggleNav}
        >
          {navOpen ? <PanelLeftClose size={16} aria-hidden /> : <Menu size={16} aria-hidden />}
          <span className="sr-only">{navOpen ? t("app.menuClose") : t("app.menu")}</span>
        </button>
        <div className="topbar__brand">
          <span className="topbar__mark" aria-hidden />
          <Radio size={16} aria-hidden />
          <strong>{t("app.name")}</strong>
          <span className="muted">{t("app.desk")}</span>
        </div>

        <div className="topbar__right">
          <LangSwitcher />
          <span className="topbar__user">{me.email}</span>
          <span className={roleChip(me.role)}>{lookup(t, "role", me.role)}</span>
          <button type="button" className="btn btn--ghost" onClick={signOut}>
            <LogOut size={14} aria-hidden /> {t("app.signOut")}
          </button>
        </div>
      </header>

      {navOpen ? (
        <button type="button" className="sidebar-scrim" aria-label={t("app.menuClose")} onClick={toggleNav} />
      ) : null}

      <div className="shell__row">
        <nav id="desk-nav" className="sidebar" aria-label="Primary">
          <p className="sidebar__group">{t("nav.groupNow")}</p>
          <NavBtn
            collapsed={!navOpen}
            active={view.name === "live" || view.name === "alert" || view.name === "unit"}
            icon={<Map size={16} />}
            label={t("nav.map")}
            hint={t("cmd.mapHint")}
            onClick={() => setView({ name: "live" })}
          />
          {writeRoles && (
            <NavBtn
              collapsed={!navOpen}
              active={view.name === "compose"}
              icon={<PenLine size={16} />}
              label={t("nav.write")}
              hint={t("cmd.writeHint")}
              onClick={() => setView({ name: "compose" })}
            />
          )}
          {writeRoles && (
            <NavBtn
              collapsed={!navOpen}
              active={view.name === "queue"}
              icon={<HeartPulse size={16} />}
              label={t("nav.help")}
              hint={t("cmd.helpHint")}
              onClick={() => setView({ name: "queue" })}
            />
          )}
          {relayRoles && (
            <NavBtn
              collapsed={!navOpen}
              active={view.name === "relay"}
              icon={<Footprints size={16} />}
              label={t("nav.foot")}
              hint={t("cmd.footHint")}
              onClick={() => setView({ name: "relay" })}
            />
          )}
          <NavBtn
            collapsed={!navOpen}
            active={view.name === "incident"}
            icon={<Siren size={16} />}
            label={t("nav.emergency")}
            hint={t("cmd.emergencyHint")}
            onClick={() => {
              if (lastIncidentId) openIncident(lastIncidentId);
              else setView({ name: "board" });
            }}
          />
          <NavBtn
            collapsed={!navOpen}
            active={view.name === "board"}
            icon={<LayoutDashboard size={16} />}
            label={t("nav.overview")}
            hint={t("cmd.overviewHint")}
            onClick={() => setView({ name: "board" })}
          />

          <p className="sidebar__group">{t("nav.groupAlso")}</p>
          {writeRoles && (
            <NavBtn
              collapsed={!navOpen}
              active={view.name === "enroll"}
              icon={<UserPlus size={16} />}
              label={t("nav.register")}
              hint={t("cmd.registerHint")}
              onClick={() => setView({ name: "enroll" })}
            />
          )}
          <NavBtn
            collapsed={!navOpen}
            active={view.name === "method"}
            icon={<BookOpen size={16} />}
            label={t("nav.measure")}
            onClick={() => setView({ name: "method" })}
          />
          <NavBtn
            collapsed={!navOpen}
            active={view.name === "analytics"}
            icon={<Clock size={16} />}
            label={t("nav.timing")}
            onClick={() => setView({ name: "analytics" })}
          />
        </nav>

        <main id="desk" className="shell__body" tabIndex={-1}>
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
      </div>

      <CommandPalette commands={commands} emptyLabel={t("cmd.none")} searchLabel={t("app.search")} />
    </div>
  );
}
