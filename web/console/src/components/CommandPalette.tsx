/** The command palette (Ctrl+K / ⌘K) — Part 0.4.3.
 *
 * THE PROBLEM IT SOLVES, in the spec's words: "Twenty-eight core features
 * cannot live in a navigation bar. The two obvious answers both fail: a wall
 * of icons is unlearnable, and three levels of nesting means an officer hunts
 * for a control during the ten minutes it matters."
 *
 * So: navigation holds ONLY the five screens used DURING an event. Everything
 * else is one keystroke. On the Linear / Superhuman / Raycast model.
 *
 * "Every command carries its keyboard shortcut in the palette, so the palette
 *  TEACHES the shortcuts and an officer graduates off it." — that is why the
 * shortcut is rendered on the right of each row rather than hidden in a help
 * screen.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";

export interface Command {
  id: string;
  label: string;
  hint?: string;
  /** Rendered right-aligned so the palette teaches the shortcut. */
  shortcut?: string;
  run: () => void;
}

export function CommandPalette({ commands }: { commands: Command[] }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
        setQuery("");
        setActive(0);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter(
      (c) =>
        c.label.toLowerCase().includes(q) || c.hint?.toLowerCase().includes(q),
    );
  }, [commands, query]);

  if (!open) return null;

  function runAt(i: number) {
    const cmd = filtered[i];
    if (!cmd) return;
    setOpen(false);
    cmd.run();
  }

  return (
    <div
      className="palette__scrim"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={() => setOpen(false)}
    >
      {/* Angular, corner-cut — a "mission briefing" panel, not a rounded
          centered modal (Part 0.5). */}
      <div className="palette panel panel--raised" onClick={(e) => e.stopPropagation()}>
        <div className="palette__input">
          <Search size={16} aria-hidden />
          <input
            ref={inputRef}
            value={query}
            placeholder="Type a command…"
            aria-label="Command"
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, filtered.length - 1));
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              }
              if (e.key === "Enter") {
                e.preventDefault();
                runAt(active);
              }
            }}
          />
        </div>
        <ul className="palette__list" role="listbox">
          {filtered.length === 0 && (
            <li className="palette__empty muted">No matching command</li>
          )}
          {filtered.map((c, i) => (
            <li
              key={c.id}
              role="option"
              aria-selected={i === active}
              className={`palette__item ${i === active ? "is-active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => runAt(i)}
            >
              <span>{c.label}</span>
              {c.hint && <span className="muted palette__hint">{c.hint}</span>}
              {c.shortcut && <kbd className="mono">{c.shortcut}</kbd>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
