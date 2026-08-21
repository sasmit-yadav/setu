/** Login.
 *
 * Deliberately plain. Part 0.4.8 forbids the "generic-SaaS landing aesthetic —
 * gradient hero, glassmorphism, floating cards", and a login screen is exactly
 * where that instinct usually wins. One angular panel, one accent, no hero.
 */

import { useState } from "react";
import { ApiError, endpoints } from "../lib/api";

export function Login({ onAuthed }: { onAuthed: () => void }) {
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
      // The API returns one uniform 401 for every credential failure, on
      // purpose (account enumeration). The UI must not invent a more specific
      // message than the server was willing to give.
      if (err instanceof ApiError && err.status === 401) {
        setError("Those credentials were not accepted.");
      } else if (err instanceof ApiError && err.status === 503) {
        setError("Authentication is not configured on this server.");
      } else {
        setError("Could not reach the API.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <form className="login__panel panel panel--raised" onSubmit={submit}>
        <div className="login__brand">
          <span className="topbar__mark" aria-hidden />
          <p className="screen__kicker">Authorized access</p>
          <h1>SETU</h1>
        </div>
        <p className="muted">Operations console</p>

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className="field">
          <span>Password</span>
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

        <button className="btn btn--primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <p className="muted login__note">
          Accounts are provisioned by an administrator. There is no
          self-registration on a system that can order an evacuation.
        </p>
      </form>
    </main>
  );
}
