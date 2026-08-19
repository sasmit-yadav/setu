/** Severity badge.
 *
 * Part 11.1's hard requirement: "Every severity and state carries an icon AND
 * a text label, never colour alone — a hard requirement for red/green
 * colour-blind users on a life-safety tool."
 *
 * The ambient glow on `extreme` is the ONE flourish in the product (Part 0.5:
 * "reserve glow for exactly one severity tier"). It lives in base.css so the
 * rule stays in one place, and it is removed under prefers-reduced-motion.
 */

import { AlertCircle, AlertOctagon, AlertTriangle, HelpCircle, Info } from "lucide-react";
import type { Severity } from "../lib/api";

const MAP = {
  extreme: { Icon: AlertOctagon, label: "Extreme" },
  severe: { Icon: AlertTriangle, label: "Severe" },
  moderate: { Icon: AlertCircle, label: "Moderate" },
  minor: { Icon: Info, label: "Minor" },
} as const;

/** Anything the CAP feed gave us that is not one of the four canonical tiers.
 *
 * `unknown` is a REAL value in this database — 24 alerts carry it, mostly from
 * GDACS events whose alert level did not map onto our scale. This component
 * originally fell back to MAP.minor, which rendered them as "Minor": a
 * severity we do not know, displayed as the LOWEST severity we have. On a
 * life-safety console that is not a cosmetic bug — it invites an officer to
 * deprioritise an alert whose actual severity was never established.
 *
 * Same principle as the assurance ladder's struck-through rung: a missing
 * signal and a negative signal are different facts and must never render
 * identically. "Unknown" gets its own icon, its own label and its own neutral
 * styling, so it reads as a gap in the data rather than as reassurance.
 */
const UNKNOWN = { Icon: HelpCircle, label: "Unknown" } as const;

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const known = MAP[severity as Severity];
  const { Icon, label } = known ?? UNKNOWN;
  const cls = known ? `sev--${severity}` : "sev--unknown";
  return (
    <span className={`sev ${cls}`} title={known ? undefined : `Source severity: ${severity}`}>
      <Icon size={12} aria-hidden />
      {label}
    </span>
  );
}
