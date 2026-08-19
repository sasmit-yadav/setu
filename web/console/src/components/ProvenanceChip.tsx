/** Provenance chips (Part 11.1).
 *
 * All five answer one question: where did this actually come from? They share
 * a visual family on purpose — an officer who learns to read the SIM badge has
 * already learned to read HUMAN and PEER.
 *
 * Part 0.4.8 forbids emoji as iconography anywhere, so the "⇄" for peer relay
 * is drawn with lucide's ArrowLeftRight rather than a character that renders
 * differently on every platform and reads as an emoji to a screen reader.
 */

import { ArrowLeftRight, CircleDot, FlaskConical, ShieldCheck, User } from "lucide-react";

const KINDS = {
  simulated: {
    cls: "chip--sim",
    label: "SIM",
    Icon: FlaskConical,
    title: "Simulated carrier — flagged simulated=true in the database",
  },
  humanRelay: {
    cls: "chip--human",
    label: "HUMAN",
    Icon: User,
    // Rule 9: a human attestation is never rendered as a digital receipt.
    title: "Confirmed by a person, not a digital receipt",
  },
  peerRelay: {
    cls: "chip--peer",
    label: "PEER",
    Icon: ArrowLeftRight,
    title: "Received via a nearby device, signature verified",
  },
  bootstrapML: {
    cls: "chip--bootstrap",
    label: "BOOTSTRAP",
    Icon: FlaskConical,
    title: "Model trained on a published physical process, not on outcomes",
  },
  authoritative: {
    cls: "chip--auto",
    label: "AUTO-AUTH",
    Icon: ShieldCheck,
    // Rule 12: the seismograph is the second pair of eyes.
    title: "Approved by an authoritative source, not a human",
  },
  live: {
    cls: "chip--peer",
    label: "LIVE",
    Icon: CircleDot,
    title: "Streaming from the server",
  },
} as const;

export type ProvenanceKind = keyof typeof KINDS;

export function ProvenanceChip({ kind }: { kind: ProvenanceKind }) {
  const { cls, label, Icon, title } = KINDS[kind];
  return (
    <span className={`chip ${cls}`} title={title}>
      <Icon size={11} aria-hidden />
      {label}
      {/* The tooltip is not accessible on its own, so the meaning is also
          available to assistive tech. */}
      <span className="sr-only">. {title}</span>
    </span>
  );
}
