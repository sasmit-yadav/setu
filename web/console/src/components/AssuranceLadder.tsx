/** B8 — the Delivery Assurance Ladder.
 *
 * Reference (Part 0.4.5/0.4.6): WhatsApp's tick system + Stripe's payment
 * timeline. A billion people already understand an ascending delivery-evidence
 * ladder because WhatsApp spent a decade teaching it — we borrow the MENTAL
 * MODEL, not the glyphs.
 *
 * The rule this component exists to carry (Rule 8, Part 0.5's third v3.0
 * visual beat):
 *
 *   A rung a channel CANNOT PROVE is struck through, with the reason beside
 *   it — NOT greyed out (reads as "loading") and NOT hidden (reads as "we
 *   didn't check"). Struck through with a reason is the only honest
 *   rendering, and it is the single most GOV.UK-correct component in the
 *   product.
 *
 * Nothing about channel capability is hardcoded here. `supported` and the
 * verbatim `reason` come from channel_capability_tier via
 * GET /alerts/{id}/assurance. That is deliberate: the moment this file
 * contains a list of what SMS can do, the database stops being the source of
 * truth and Rule 8 becomes a comment rather than a constraint.
 */

import {
  ArrowUpRight,
  Check,
  Circle,
  Eye,
  MessageSquare,
  Slash,
  Smartphone,
} from "lucide-react";
import type { DeliveryAssurance, Rung } from "../lib/api";
import { ProvenanceChip } from "./ProvenanceChip";

const ICON_SIZE = 14;

/** Tier metadata. Level ordering mirrors assurance_level() in SQL — the
 *  ladder's definition, which Part 38 lists as legitimately staying in code
 *  (it is what the ladder IS, not a threshold anyone would tune). */
const TIER = {
  provider_accept: { label: "Provider accepted", Icon: ArrowUpRight },
  device_delivered: { label: "Device delivered", Icon: Smartphone },
  opened: { label: "Opened", Icon: Eye },
  acknowledgement: { label: "Acknowledged", Icon: Check },
} as const;

function formatTime(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function RungRow({ rung }: { rung: Rung }) {
  const meta = TIER[rung.tier];
  if (!meta) return null;
  const { label, Icon } = meta;

  if (rung.status === "not_applicable") {
    return (
      <li className="rung rung--na">
        <Slash size={ICON_SIZE} aria-hidden />
        {/* <s> carries the meaning to assistive tech as well as to the eye.
            The sr-only text guarantees a screen reader announces "not
            applicable" rather than reading a struck label as if it were a
            normal one (Part 0.4.7). */}
        <s>{label}</s>
        <span className="sr-only">— not applicable</span>
        {/* Verbatim from channel_capability_tier.not_applicable_reason.
            THIS SENTENCE IS THE PRODUCT. */}
        {rung.reason && <span className="rung__reason">{rung.reason}</span>}
      </li>
    );
  }

  if (rung.status === "recorded") {
    return (
      <li className="rung rung--reached">
        <Icon size={ICON_SIZE} aria-hidden />
        <span>{label}</span>
        <time className="mono" dateTime={rung.occurred_at}>
          {formatTime(rung.occurred_at)}
        </time>
        {rung.source && <span className="rung__src muted">{rung.source}</span>}
      </li>
    );
  }

  // pending: the evidence has not arrived. An empty circle and an em dash —
  // never a spinner. Part 0.5's guardrail: no progress indicator may ever be
  // shown for a signal the platform does not actually have.
  return (
    <li className="rung rung--pending">
      <Circle size={ICON_SIZE} aria-hidden />
      <span>{label}</span>
      <span className="muted mono">—</span>
    </li>
  );
}

export function AssuranceLadder({ delivery }: { delivery: DeliveryAssurance }) {
  return (
    <div className="ladder">
      <header className="ladder__head">
        <span className="ladder__channel mono">{delivery.channel_code.toUpperCase()}</span>
        <span className="muted mono">#{delivery.delivery_id}</span>
        {/* Every simulated delivery is flagged in the DB and badged on
            screen (§8.5). We never pretend. */}
        {delivery.simulated && <ProvenanceChip kind="simulated" />}
        <span className="ladder__state muted">{delivery.state}</span>
      </header>
      <ol className="ladder__rungs" aria-label={`Delivery assurance for ${delivery.channel_code}`}>
        {delivery.rungs.map((r) => (
          <RungRow key={r.tier} rung={r} />
        ))}
      </ol>
      {/* citizen_response (tier 5) sits above the four capability tiers and
          is not part of channel_capability, so it is shown only when the
          derived level actually reached it. */}
      {delivery.assurance_level >= 5 && (
        <div className="rung rung--reached">
          <MessageSquare size={ICON_SIZE} aria-hidden />
          <span>Response received</span>
        </div>
      )}
    </div>
  );
}
