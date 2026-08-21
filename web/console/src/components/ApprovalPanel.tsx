import { ShieldCheck, Square, UserCheck } from "lucide-react";
import { ProvenanceChip } from "./ProvenanceChip";
import { useT } from "../lib/i18n";

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
  authoritative?: boolean;
  onApprove?: () => void;
  approving?: boolean;
  selfAlreadyApproved?: boolean;
}) {
  const { t } = useT();
  if (authoritative) {
    return (
      <section className="approval" aria-label={t("approval.ok")}>
        <header className="approval__head">
          <ShieldCheck size={16} className="ok" aria-hidden />
          <strong>{t("approval.bySource")}</strong>
          <ProvenanceChip kind="authoritative" />
        </header>
        <p className="muted approval__note">{t("approval.bySourceNote", { need })}</p>
      </section>
    );
  }

  const slots = Array.from({ length: need }, (_, i) => i < have);
  const satisfied = have >= need;

  return (
    <section className="approval" aria-label={t("approval.ok")}>
      <header className="approval__head">
        {satisfied ? (
          <ShieldCheck size={16} className="ok" aria-hidden />
        ) : (
          <UserCheck size={16} className="warn" aria-hidden />
        )}
        <strong className={satisfied ? "ok" : undefined}>
          {satisfied ? t("approval.ok") : t("approval.wait", { have, need })}
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
                <span>{t("approval.slotOk", { n: i + 1 })}</span>
              </>
            ) : (
              <>
                <Square size={ICON} aria-hidden />
                <span>{t("approval.slotNeed", { n: i + 1 })}</span>
                <span className="sr-only">— {t("approval.missing")}</span>
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
            {approving ? t("approval.signing") : t("approval.sign")}
          </button>
          {selfAlreadyApproved && (
            <p className="approval__note muted">{t("approval.already")}</p>
          )}
        </>
      )}
    </section>
  );
}
