import { useState } from "react";
import { ApiError, endpoints } from "../lib/api";
import { useT } from "../lib/i18n";
import { LangSwitcher } from "../components/LangSwitcher";

export function Login({ onAuthed }: { onAuthed: () => void }) {
  const { t } = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await endpoints.login(email, password);
      onAuthed();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t("login.bad"));
      } else if (err instanceof ApiError && err.status === 503) {
        setError(t("login.down"));
      } else {
        setError(t("login.offline"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <form className="login__panel panel panel--raised" onSubmit={submit}>
        <div className="login__lang">
          <LangSwitcher />
        </div>
        <div className="login__brand">
          <span className="topbar__mark" aria-hidden />
          <p className="screen__kicker">{t("login.kicker")}</p>
          <h1>{t("login.title")}</h1>
        </div>
        <p className="lede">{t("login.subtitle")}</p>

        <label className="field">
          <span>{t("login.email")}</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className="field">
          <span>{t("login.password")}</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && (
          <p className="login__error danger" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn--primary" disabled={busy} aria-busy={busy}>
          {busy ? t("login.busy") : t("login.submit")}
        </button>

        <p className="muted login__note">{t("login.note")}</p>
      </form>
    </main>
  );
}
