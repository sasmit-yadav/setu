import { ArrowLeftRight, CircleDot, FlaskConical, ShieldCheck, User } from "lucide-react";
import { useT } from "../lib/i18n";

const KINDS = {
  simulated: { cls: "chip--sim", label: "chip.simulated", title: "chip.simulatedTitle", Icon: FlaskConical },
  humanRelay: { cls: "chip--human", label: "chip.humanRelay", title: "chip.humanRelayTitle", Icon: User },
  peerRelay: { cls: "chip--peer", label: "chip.peerRelay", title: "chip.peerRelayTitle", Icon: ArrowLeftRight },
  bootstrapML: { cls: "chip--bootstrap", label: "chip.bootstrapML", title: "chip.bootstrapMLTitle", Icon: FlaskConical },
  authoritative: { cls: "chip--auto", label: "chip.authoritative", title: "chip.authoritativeTitle", Icon: ShieldCheck },
  live: { cls: "chip--peer", label: "chip.live", title: "chip.liveTitle", Icon: CircleDot },
} as const;

export type ProvenanceKind = keyof typeof KINDS;

export function ProvenanceChip({ kind }: { kind: ProvenanceKind }) {
  const { t } = useT();
  const { cls, label, Icon, title } = KINDS[kind];
  const meaning = t(title);
  return (
    <span className={`chip ${cls}`} title={meaning}>
      <Icon size={11} aria-hidden />
      {t(label)}
      <span className="sr-only">. {meaning}</span>
    </span>
  );
}
