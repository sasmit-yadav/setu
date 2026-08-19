/** F1 — the pre-dispatch quality gate.
 *
 * Reference (Part 0.4.6): GitHub PR checks / Vercel deploy checks —
 * *"Merging is blocked — 1 check failed"* with the failing check NAMED.
 * Part 0.5's first v3.0 visual beat spells out the rest:
 *
 *   "Reads as a pre-flight checklist, not an error toast. Six rows, each with
 *    ✓/✗ and the exact failing reason. A blocked dispatch button with the
 *    reason ADJACENT to it, never a dismissible red banner the officer can
 *    click past. Failing a gate must feel like a seatbelt, not a nag."
 *
 * So: no toast, no dismissal, no auto-hide. The list is always visible and the
 * reason lives next to the button it is blocking.
 */

import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import type { RuleResult } from "../lib/api";

const ICON = 15;

/** Human-readable names for the six rules. The rule_id is the contract; this
 *  is only presentation, and falls back to the id so a NEW rule added
 *  server-side still renders something truthful rather than blank. */
const RULE_LABEL: Record<string, string> = {
  geometry_non_empty: "Alert area has geometry",
  expiry_set: "Expiry timestamp set",
  target_count_plausible: "Targets at least one recipient",
  escalation_policy_exists: "Escalation policy exists for this severity",
  translation_exists: "Required translation present",
  target_area_plausible: "Target area within plausible size",
};

function RuleRow({ rule }: { rule: RuleResult }) {
  const label = RULE_LABEL[rule.rule_id] ?? rule.rule_id;
  if (rule.status === "pass") {
    return (
      <li className="gate__row">
        <CheckCircle2 size={ICON} className="ok" aria-hidden />
        <span>{label}</span>
        <span className="sr-only">— passed</span>
      </li>
    );
  }
  if (rule.status === "warn") {
    // A warn does NOT block. quality_gate.max_target_area_km2 is a WARN, not a
    // BLOCK, because a genuine cyclone warning can legitimately be huge — so a
    // human decides and we only flag (see that key's note in app_config).
    return (
      <li className="gate__row gate__row--warn">
        <AlertTriangle size={ICON} className="warn" aria-hidden />
        <span>{label}</span>
        <span className="sr-only">— warning</span>
        {rule.message && <span className="gate__msg muted">{rule.message}</span>}
      </li>
    );
  }
  return (
    <li className="gate__row gate__row--fail">
      <XCircle size={ICON} className="danger" aria-hidden />
      <span>{label}</span>
      <span className="sr-only">— failed</span>
      {/* The exact failing reason, named. This is the whole borrowed pattern. */}
      {rule.message && <span className="gate__msg danger">{rule.message}</span>}
    </li>
  );
}

export function QualityGate({
  results,
  blocked,
}: {
  results: RuleResult[];
  blocked: boolean;
}) {
  const failed = results.filter((r) => r.status === "fail");
  return (
    <section className="gate" aria-label="Pre-dispatch quality gate">
      <header className="gate__head">
        {blocked ? (
          <>
            <XCircle size={16} className="danger" aria-hidden />
            <strong className="danger">
              Dispatch blocked — {failed.length} check{failed.length === 1 ? "" : "s"} failed
            </strong>
          </>
        ) : (
          <>
            <CheckCircle2 size={16} className="ok" aria-hidden />
            <strong className="ok">All {results.length} checks passed</strong>
          </>
        )}
      </header>
      <ol className="gate__rows">
        {results.map((r) => (
          <RuleRow key={r.rule_id} rule={r} />
        ))}
      </ol>
    </section>
  );
}
