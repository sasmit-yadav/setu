/** App shell.
 *
 * Navigation holds ONLY the screens used DURING an event (Part 0.4.3).
 * Everything else is a command-palette entry, because "three levels of nesting
 * means an officer hunts for a control during the ten minutes it matters".
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Command, LogOut, Radio } from "lucide-react";
import { endpoints, getToken, setToken, type Me } from "./lib/api";
import { CommandPalette, type Command as Cmd } from "./components/CommandPalette";
import { Login } from "./pages/Login";
import { LiveOps } from "./pages/LiveOps";
import { AlertDetail } from "./pages/AlertDetail";

type View = { name: "live" } | { name: "alert"; id: number };

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const [view, setView] = useState<View>({ name: "live" });

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

  const commands: Cmd[] = useMemo(
    () => [
      {
        id: "live",
        label: "Go to Live Operations",
        hint: "alerts, delivery status",
        shortcut: "G L",
        run: () => setView({ name: "live" }),
      },
      {
        id: "signout",
        label: "Sign out",
        hint: me?.email,
        run: signOut,
      },
    ],
    [me],
  );

  if (!checked) return null;
  if (!me) return <Login onAuthed={() => void loadMe()} />;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__brand">
          <Radio size={16} aria-hidden />
          <strong>SETU</strong>
          <span className="muted">Operations Console</span>
        </div>

        <nav className="topbar__nav" aria-label="Primary">
          <button
            className={`navlink ${view.name === "live" ? "is-active" : ""}`}
            onClick={() => setView({ name: "live" })}
          >
            Live Operations
          </button>
        </nav>

        <div className="topbar__right">
          {/* The palette advertises itself — Part 0.4.3: it teaches the
              shortcuts so the officer graduates off it. */}
          <span className="topbar__hint muted">
            <Command size={12} aria-hidden /> <kbd className="mono">Ctrl K</kbd>
          </span>
          <span className="topbar__user mono">{me.email}</span>
          <span className="chip chip--sim">{me.role}</span>
          <button className="btn btn--ghost" onClick={signOut} aria-label="Sign out">
            <LogOut size={14} aria-hidden />
          </button>
        </div>
      </header>

      <main className="shell__body">
        {view.name === "live" && (
          <LiveOps onOpen={(id) => setView({ name: "alert", id })} />
        )}
        {view.name === "alert" && (
          <AlertDetail id={view.id} onBack={() => setView({ name: "live" })} />
        )}
      </main>

      <CommandPalette commands={commands} />
    </div>
  );
}
