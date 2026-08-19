/** F3 — dual authorization (Four-Eyes).
 *
 * Reference (Part 0.4.6): GitHub PR reviews — *"1 approval required"* — a
 * familiar, non-bureaucratic way to show a MISSING signature.
 *
 * Part 0.5's second v3.0 visual beat is unusually specific, and it inverts the
 * normal instinct:
 *
 *   "The approval panel is the one place in the console that is deliberately,
 *    visibly INCOMPLETE until a second human acts. `✓ Officer A / ☐ Officer B`
 *    with the empty checkbox rendered AT FULL CONTRAST, not greyed — the UI's
 *    job here is to make the missing signature the loudest thing on screen."
 *
 * Hence `.approval__slot--missing` uses --text-primary and a solid border,
 * while the SATISFIED slot is the quieter one. Greying the empty slot would
 * make the gap recede, which is the opposite of what this panel is for.
 */

import { ShieldCheck, Square, UserCheck } from "lucide-react";
import { ProvenanceChip } from "./ProvenanceChip";

const ICON = 15;

export function ApprovalPanel({
  have,
  need,
  authoritative,
  onApprove,
  approving,
  selfAlreadyApproved,
}: {
  have: number;
  need: number;
  /** Rule 12: an alert from an is_authoritative source dispatches with
   *  provenance='authoritative_source' and no human wait. The seismograph IS
   *  the second pair of eyes. */
  authoritative?: boolean;
  onApprove?: () => void;
  approving?: boolean;
  selfAlreadyApproved?: boolean;
}) {
  if (authoritative) {
    return (
      <section className="approval" aria-label="Authorization">
        <header className="approval__head">
          <ShieldCheck size={16} className="ok" aria-hidden />
          <strong>Authorized by source</strong>
          <ProvenanceChip kind="authoritative" />
        </header>
        <p className="muted approval__note">
          Machine origin records machine provenance — an authoritative feed
          dispatches without waiting for a human. A human-composed alert of the
          same severity would require {need} approvals.
        </p>
      </section>
    );
  }

  const slots = Array.from({ length: need }, (_, i) => i < have);
  const satisfied = have >= need;

  return (
    <section className="approval" aria-label="Authorization">
      <header className="approval__head">
        {satisfied ? (
          <ShieldCheck size={16} className="ok" aria-hidden />
        ) : (
          <UserCheck size={16} className="warn" aria-hidden />
        )}
        <strong className={satisfied ? "ok" : undefined}>
          {satisfied
            ? "Authorized"
            : `Awaiting authorization — ${have} of ${need}`}
        </strong>
      </header>

      <ol className="approval__slots">
        {slots.map((filled, i) => (
          <li
            key={i}
            className={`approval__slot ${filled ? "approval__slot--filled" : "approval__slot--missing"}`}
          >
            {filled ? (
              <>
                <ShieldCheck size={ICON} aria-hidden />
                <span>Approval {i + 1} recorded</span>
              </>
            ) : (
              <>
                <Square size={ICON} aria-hidden />
                <span>Approval {i + 1} required</span>
                <span className="sr-only">— missing</span>
              </>
            )}
          </li>
        ))}
      </ol>

      {!satisfied && onApprove && (
        <>
          <button
            className="btn btn--approve"
            onClick={onApprove}
            disabled={approving || selfAlreadyApproved}
          >
            {approving ? "Recording…" : "Approve as me"}
          </button>
          {/* The reason a control is unavailable sits ADJACENT to it, never in
              a toast. Same rule as the quality gate's blocked dispatch. */}
          {selfAlreadyApproved && (
            <p className="approval__note muted">
              You have already approved this alert. The second approval must
              come from a different officer — the database enforces it
              (UNIQUE on alert and approver), so clicking again cannot satisfy
              the quorum.
            </p>
          )}
        </>
      )}
    </section>
  );
}
