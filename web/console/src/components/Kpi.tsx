/** KPI strip (Part 11.2's Live Operations header).
 *
 * Part 0.5: "KPI numbers in the header strip count up over ~400ms when they
 * change — motion as CONFIRMATION, not decoration, and prefers-reduced-motion
 * collapses every one of these to instant, no exceptions."
 *
 * The count-up is therefore driven by --dur-count, which tokens.css already
 * sets to 0ms under prefers-reduced-motion. One place to honour the setting.
 */

import { useEffect, useRef, useState } from "react";

function useCountUp(target: number): number {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);

  useEffect(() => {
    const durMs = Number(
      getComputedStyle(document.documentElement)
        .getPropertyValue("--dur-count")
        .replace("ms", "")
        .trim() || 0,
    );
    const from = fromRef.current;
    if (durMs === 0 || from === target) {
      fromRef.current = target;
      setValue(target);
      return;
    }
    let raf = 0;
    const started = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / durMs);
      // easeOutQuad: fast then settling — reads as the number ARRIVING.
      const eased = 1 - (1 - t) * (1 - t);
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  return value;
}

export function Kpi({
  label,
  value,
  tone,
  note,
}: {
  label: string;
  value: number;
  tone?: "ok" | "danger" | "warn" | "info";
  /** Part 0.5's guardrail: "An 88% that is really '88% of the tiers we can
   *  measure' must say so in the label." A KPI whose meaning is partial says
   *  so here, in the tile, not in a footnote. */
  note?: string;
}) {
  const shown = useCountUp(value);
  return (
    <div className={`kpi${tone ? ` kpi--${tone}` : ""}`}>
      <span className="kpi__label">{label}</span>
      <span className={`kpi__value mono ${tone ? tone : ""}`}>
        {shown.toLocaleString()}
      </span>
      {note && <span className="kpi__note muted">{note}</span>}
    </div>
  );
}
