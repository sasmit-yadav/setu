import { AlertCircle, AlertOctagon, AlertTriangle, HelpCircle, Info } from "lucide-react";
import type { Severity } from "../lib/api";
import { useT } from "../lib/i18n";

const MAP = {
  extreme: { Icon: AlertOctagon, key: "sev.extreme" },
  severe: { Icon: AlertTriangle, key: "sev.severe" },
  moderate: { Icon: AlertCircle, key: "sev.moderate" },
  minor: { Icon: Info, key: "sev.minor" },
} as const;

const UNKNOWN = { Icon: HelpCircle, key: "sev.unknown" } as const;

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const { t } = useT();
  const known = MAP[severity as Severity];
  const { Icon, key } = known ?? UNKNOWN;
  const cls = known ? `sev--${severity}` : "sev--unknown";
  const label = t(key);
  return (
    <span className={`sev ${cls}`} title={known ? undefined : `${label}: ${severity}`}>
      <Icon size={12} aria-hidden />
      {label}
    </span>
  );
}
