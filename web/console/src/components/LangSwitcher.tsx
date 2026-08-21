import { useT, type Lang } from "../lib/i18n";

export function LangSwitcher() {
  const { lang, setLang, t } = useT();
  return (
    <label className="lang-switch">
      <span className="sr-only">{t("lang.label")}</span>
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value as Lang)}
        aria-label={t("lang.label")}
      >
        <option value="en">{t("lang.en")}</option>
        <option value="hi">{t("lang.hi")}</option>
        <option value="ml">{t("lang.ml")}</option>
        <option value="mr">{t("lang.mr")}</option>
      </select>
    </label>
  );
}
