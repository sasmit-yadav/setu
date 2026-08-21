import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import type { RuleResult } from "../lib/api";
import { useT } from "../lib/i18n";

const ICON = 15;

const RULE_KEY: Record<string, string> = {
  geometry_non_empty: "gate.geometry_non_empty",
  expiry_set: "gate.expiry_set",
  target_count_plausible: "gate.target_count_plausible",
  escalation_policy_exists: "gate.escalation_policy_exists",
  translation_exists: "gate.translation_exists",
  target_area_plausible: "gate.target_area_plausible",
};

function RuleRow({ rule }: { rule: RuleResult }) {
  const { t } = useT();
  const label = RULE_KEY[rule.rule_id] ? t(RULE_KEY[rule.rule_id]) : rule.rule_id;
  if (rule.status === "pass") {
    return (
      <li className="gate__row">
        <CheckCircle2 size={ICON} className="ok" aria-hidden />
        <span>{label}</span>
        <span className="sr-only">— {t("gate.pass")}</span>
      </li>
    );
  }
  if (rule.status === "warn") {
    return (
      <li className="gate__row gate__row--warn">
        <AlertTriangle size={ICON} className="warn" aria-hidden />
        <span>{label}</span>
        <span className="sr-only">— {t("gate.warn")}</span>
        {rule.message && <span className="gate__msg muted">{rule.message}</span>}
      </li>
    );
  }
  return (
    <li className="gate__row gate__row--fail">
      <XCircle size={ICON} className="danger" aria-hidden />
      <span>{label}</span>
      <span className="sr-only">— {t("gate.fail")}</span>
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
  const { t } = useT();
  const failed = results.filter((r) => r.status === "fail");
  return (
    <section className="gate" aria-label={t("gate.title")}>
      <header className="gate__head">
        {blocked ? (
          <>
            <XCircle size={16} className="danger" aria-hidden />
            <strong className="danger">
              {failed.length === 1
                ? t("gate.blocked", { n: failed.length })
                : t("gate.blockedMany", { n: failed.length })}
            </strong>
          </>
        ) : (
          <>
            <CheckCircle2 size={16} className="ok" aria-hidden />
            <strong className="ok">{t("gate.passed", { n: results.length })}</strong>
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
