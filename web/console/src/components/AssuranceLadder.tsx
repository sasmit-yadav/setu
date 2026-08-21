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
import { lookup, useT } from "../lib/i18n";
import { ProvenanceChip } from "./ProvenanceChip";

const ICON_SIZE = 14;

const TIER = {
  provider_accept: { key: "ladder.provider_accept", Icon: ArrowUpRight },
  device_delivered: { key: "ladder.device_delivered", Icon: Smartphone },
  opened: { key: "ladder.opened", Icon: Eye },
  acknowledgement: { key: "ladder.acknowledgement", Icon: Check },
} as const;

function formatTime(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function RungRow({ rung }: { rung: Rung }) {
  const { t } = useT();
  const meta = TIER[rung.tier];
  if (!meta) return null;
  const { key, Icon } = meta;
  const label = t(key);

  if (rung.status === "not_applicable") {
    return (
      <li className="rung rung--na">
        <Slash size={ICON_SIZE} aria-hidden />
        <s>{label}</s>
        <span className="sr-only">— not applicable</span>
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

  return (
    <li className="rung rung--pending">
      <Circle size={ICON_SIZE} aria-hidden />
      <span>{label}</span>
      <span className="muted mono">—</span>
    </li>
  );
}

export function AssuranceLadder({ delivery }: { delivery: DeliveryAssurance }) {
  const { t } = useT();
  const channel = lookup(t, "channel", delivery.channel_code);
  const state = lookup(t, "state", delivery.state);
  return (
    <div className="ladder">
      <header className="ladder__head">
        <span className="ladder__channel">{channel}</span>
        <span className="muted mono">#{delivery.delivery_id}</span>
        {delivery.simulated && <ProvenanceChip kind="simulated" />}
        <span className="ladder__state muted">{state}</span>
      </header>
      <ol className="ladder__rungs" aria-label={t("ladder.for", { channel })}>
        {delivery.rungs.map((r) => (
          <RungRow key={r.tier} rung={r} />
        ))}
      </ol>
      {delivery.assurance_level >= 5 && (
        <div className="rung rung--reached">
          <MessageSquare size={ICON_SIZE} aria-hidden />
          <span>{t("ladder.response")}</span>
        </div>
      )}
    </div>
  );
}
