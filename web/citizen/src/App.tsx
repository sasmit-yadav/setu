import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ApiError,
  clearCitizenSession,
  fetchDelivery,
  fetchMyDeliveries,
  fetchPublicConfig,
  fetchSafeZone,
  fetchSigningKey,
  hasCitizenSession,
  loginCitizen,
  requestCitizenOtp,
  verifyCitizenOtp,
  postAck,
  postPeerReceipt,
  postResponse,
  type CitizenDelivery,
  type PublicConfig,
  type SafeZone,
} from "./api";
import { setVerifyKey } from "./verify";
import { listenPeer, sharePeer, readPeerFromUrl, stripPeerFromUrl, acceptPeerPayload, type PeerPayload } from "./relay";
import { enablePush, pushConfigured, pushFailMessage, pushSupported, refreshPushIfGranted } from "./push";
import { speakAlert, speechSupported, stopSpeaking, unlockSpeech } from "./speak";
import "./styles.css";

type Screen = "alert" | "help" | "other" | "location";

function csv(cfg: PublicConfig | null, key: string): string[] {
  const value = cfg?.[key];
  if (typeof value !== "string" || !value.trim()) return [];
  return value.split(",").map((part) => part.trim()).filter(Boolean);
}

function cfgLabel(cfg: PublicConfig | null, id: string): string | null {
  const value = cfg?.[`response.label.${id}`];
  return typeof value === "string" && value.trim() ? value : null;
}

function cfgInt(cfg: PublicConfig | null, key: string): number | null {
  const value = cfg?.[key];
  return typeof value === "number" ? value : null;
}

function cfgOn(cfg: PublicConfig | null, key: string): boolean {
  const value = cfg?.[key];
  return value === 1 || value === "true";
}

function IconPeer() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden>
      <path
        fill="currentColor"
        d="M8 7 3 12l5 5v-3h5v-4H8V7zm8 10 5-5-5-5v3h-5v4h5v3z"
      />
    </svg>
  );
}

function Brand() {
  return (
    <p className="brand">
      <span className="brand__mark" aria-hidden />
      SETU
    </p>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      <path fill="currentColor" d="M9.2 16.2 4.8 11.8l1.4-1.4 3 3 8.6-8.6 1.4 1.4z" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      <path fill="currentColor" d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
    </svg>
  );
}

function IconNeed(id: string) {
  if (id.includes("medical")) {
    return (
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
        <path fill="currentColor" d="M19 3H5v18h14V3zm-2 10h-4v4h-2v-4H7v-2h4V7h2v4h4v2z" />
      </svg>
    );
  }
  if (id.includes("trap")) {
    return (
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
        <path fill="currentColor" d="M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3z" />
      </svg>
    );
  }
  if (id.includes("evacuat")) {
    return (
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
        <path fill="currentColor" d="M10 17 5 12l5-5v3h8v4h-8v3z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      <path fill="currentColor" d="M12 2a10 10 0 1 0 .001 20.001A10 10 0 0 0 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
    </svg>
  );
}

function deliveryFromUrl(): number | null {
  const raw = new URLSearchParams(window.location.search).get("delivery_id");
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export default function App() {
  const [signedIn, setSignedIn] = useState(() => hasCitizenSession());
  const [email, setEmail] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [useEmail, setUseEmail] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);
  const [deliveryId, setDeliveryId] = useState<number | null>(deliveryFromUrl);
  const [delivery, setDelivery] = useState<CitizenDelivery | null>(null);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [screen, setScreen] = useState<Screen>("alert");
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [otherText, setOtherText] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingType, setPendingType] = useState<string | null>(null);
  const [locBusy, setLocBusy] = useState(false);
  const [peerProvenance, setPeerProvenance] = useState(false);
  const [shelter, setShelter] = useState<SafeZone | null>(null);
  const [pushState, setPushState] = useState<"idle" | "busy" | "enabled" | "error">("idle");
  const [pushError, setPushError] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState(false);
  const [offline, setOffline] = useState(() => !navigator.onLine);

  useEffect(() => {
    void (async () => {
      try {
        const next = await fetchPublicConfig();
        setCfg(next);
        const envKey = import.meta.env.VITE_ALERT_SIGNING_PUBKEY_B64 as string | undefined;
        const key = envKey && envKey.length > 10 ? envKey : await fetchSigningKey();
        setVerifyKey(key);
      } catch {
        return;
      }
    })();
  }, []);

  useEffect(() => {
    if (emailTouched) return;
    const prefill = cfg?.["demo.citizen_email"];
    if (typeof prefill === "string" && prefill.trim()) setEmail(prefill);
  }, [cfg, emailTouched]);

  useEffect(() => {
    if (!signedIn || !delivery || !speechSupported()) return;
    const payload = {
      severity: delivery.severity,
      headline: delivery.headline,
      body: delivery.body,
      lang: delivery.lang,
    };
    const timer = window.setTimeout(() => {
      const started = speakAlert({
        ...payload,
        onend: () => setSpeaking(false),
      });
      setSpeaking(started);
    }, 400);
    return () => {
      window.clearTimeout(timer);
      stopSpeaking();
      setSpeaking(false);
    };
  }, [signedIn, delivery?.delivery_id]);

  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  const applyPeer = useCallback((payload: PeerPayload) => {
    setStatus("Peer alert received · signature verified");
    setPeerProvenance(true);
    setDelivery({
      delivery_id: payload.delivery_id,
      alert_id: payload.alert_id,
      headline: payload.headline,
      body: payload.body,
      severity: payload.severity,
      channel_code: "community_relay",
      simulated: false,
      lifecycle_status: "active",
      effective_at: payload.effective_at,
      expires_at: payload.expires_at,
      signature: payload.signature,
    });
    setDeliveryId(payload.delivery_id);
    setScreen("alert");
    if (payload.signature && payload.effective_at) {
      void postPeerReceipt({
        delivery_id: payload.delivery_id,
        alert_id: payload.alert_id,
        headline: payload.headline,
        severity: payload.severity,
        effective_at: payload.effective_at,
        signature: payload.signature,
      }).catch(() => undefined);
    }
  }, []);

  const expireSession = useCallback(() => {
    clearCitizenSession();
    setSignedIn(false);
    setDelivery(null);
    setShelter(null);
    setError(null);
  }, []);

  const loadDelivery = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const row = await fetchDelivery(id);
      setDelivery(row);
      setDeliveryId(id);
      setScreen("alert");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        expireSession();
        return;
      }
      setError(e instanceof Error ? e.message : "Failed to load alert");
      setDelivery(null);
    } finally {
      setLoading(false);
    }
  }, [expireSession]);

  useEffect(() => {
    if (!signedIn || peerProvenance) return;
    if (deliveryId !== null) void loadDelivery(deliveryId);
  }, [deliveryId, loadDelivery, signedIn, peerProvenance]);

  useEffect(() => {
    if (!signedIn || peerProvenance || deliveryId !== null) return;
    let cancelled = false;
    setLoading(true);
    void fetchMyDeliveries()
      .then((rows) => {
        if (cancelled) return;
        const first = rows[0];
        if (first) {
          setDeliveryId(first.delivery_id);
          return;
        }
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          expireSession();
          return;
        }
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [signedIn, deliveryId, peerProvenance, expireSession]);

  useEffect(() => {
    if (!signedIn || !cfg) return;
    let cancelled = false;
    void refreshPushIfGranted(cfg)
      .then((result) => {
        if (cancelled || result == null) return;
        if (result.ok) {
          setPushState("enabled");
          setPushError(null);
        }
      })
      .catch(() => {
        /* Keep the button available; a tap can retry. */
      });
    return () => {
      cancelled = true;
    };
  }, [signedIn, cfg]);

  useEffect(() => {
    if (!signedIn || deliveryId === null) return;
    void fetchSafeZone(deliveryId)
      .then(setShelter)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) {
          expireSession();
          return;
        }
        setShelter(null);
      });
  }, [deliveryId, signedIn, expireSession]);

  useEffect(() => {
    return listenPeer(applyPeer);
  }, [applyPeer]);

  useEffect(() => {
    if (!signedIn || !cfg) return;
    const payload = readPeerFromUrl();
    if (!payload) return;
    void acceptPeerPayload(payload).then((ok) => {
      if (!ok) return;
      applyPeer(payload);
      stripPeerFromUrl();
    });
  }, [signedIn, cfg, applyPeer]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "setu:delivery" && event.data.deliveryId) {
        void loadDelivery(Number(event.data.deliveryId));
      }
    };
    navigator.serviceWorker?.addEventListener("message", handler);
    return () => navigator.serviceWorker?.removeEventListener("message", handler);
  }, [loadDelivery]);

  const helpTypes = useMemo(
    () =>
      csv(cfg, "response.help_types").map((id) => ({
        id,
        label: cfgLabel(cfg, id),
      })),
    [cfg],
  );
  const locationTypes = useMemo(() => csv(cfg, "response.location_prompt_types"), [cfg]);
  const freeTextTypes = useMemo(() => csv(cfg, "response.free_text_types"), [cfg]);
  const freeTextMax = cfgInt(cfg, "response.free_text_max_chars");
  const geoTimeout = cfgInt(cfg, "response.geolocation_timeout_ms");
  const safeType = typeof cfg?.["response.safe_type"] === "string" ? cfg["response.safe_type"] : null;
  const safeLabel = cfgLabel(cfg, "safe");
  const helpLabel = cfgLabel(cfg, "help");
  const peerEnabled = cfgOn(cfg, "relay.peer_enabled");
  const peerChunk = cfgInt(cfg, "relay.peer_chunk_bytes");
  const peerService = typeof cfg?.["relay.peer_service_uuid"] === "string" ? cfg["relay.peer_service_uuid"] : "";
  const peerChar = typeof cfg?.["relay.peer_char_uuid"] === "string" ? cfg["relay.peer_char_uuid"] : "";
  const peerHops = cfgInt(cfg, "relay.peer_max_hops");
  const labelsReady = Boolean(
    safeType && safeLabel && helpLabel && helpTypes.length && helpTypes.every((item) => item.label),
  );

  const severityClass = useMemo(() => {
    if (!delivery) return "severity-minor";
    return `severity-${delivery.severity}`;
  }, [delivery]);

  async function sendResponse(
    type: string,
    extra?: { freeText?: string; lat?: number; lon?: number; locationConsent?: boolean },
  ) {
    const id = delivery?.delivery_id ?? deliveryId;
    if (!id) return;
    setStatus("Sending…");
    setPending(false);
    try {
      await postAck(id);
      await postResponse(id, type, extra);
      setStatus(type === safeType ? "Marked safe." : "Help request sent.");
      setPending(false);
      setScreen("alert");
      setPendingType(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        expireSession();
        return;
      }
      const offlineNow = !navigator.onLine || e instanceof TypeError;
      if (offlineNow && !navigator.onLine) {
        setStatus("No signal. This was not sent. When you have signal, tap Help again.");
        setPending(false);
        setScreen("alert");
        return;
      }
      setStatus("Could not send. Tap Help again — the desk will not see this until it succeeds.");
      setPending(false);
    }
  }

  async function onSafe() {
    if (!safeType) return;
    await sendResponse(safeType);
  }

  async function onHelpType(type: string) {
    if (freeTextTypes.includes(type)) {
      setScreen("other");
      return;
    }
    if (locationTypes.includes(type)) {
      setPendingType(type);
      setScreen("location");
      return;
    }
    await sendResponse(type);
  }

  async function shareLocation() {
    if (!pendingType || geoTimeout == null) return;
    setLocBusy(true);
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: geoTimeout,
        });
      });
      await sendResponse(pendingType, {
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        locationConsent: true,
      });
    } catch {
      await sendResponse(pendingType);
    } finally {
      setLocBusy(false);
    }
  }

  async function submitOther() {
    if (!otherText.trim()) return;
    const type = freeTextTypes[0];
    if (!type) return;
    await sendResponse(type, { freeText: otherText.trim() });
  }

  function loginFail(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      setLoginError("That number or code was not accepted.");
    } else if (err instanceof ApiError && err.status === 503) {
      setLoginError("Authentication is not configured on this server.");
    } else {
      setLoginError("Could not reach the API.");
    }
  }

  function onEnableAlerts() {
    setPushState("busy");
    setPushError(null);
    void enablePush(cfg)
      .then((result) => {
        if (result.ok) {
          setPushState("enabled");
          setPushError(null);
          return;
        }
        setPushState("error");
        setPushError(pushFailMessage(result.reason));
      })
      .catch((err) => {
        setPushState("error");
        setPushError(
          pushFailMessage(err instanceof Error ? err.message : "push_failed"),
        );
      });
  }

  function onReadWarning() {
    if (!delivery) return;
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    unlockSpeech();
    const started = speakAlert({
      severity: delivery.severity,
      headline: delivery.headline,
      body: delivery.body,
      lang: delivery.lang,
      onend: () => setSpeaking(false),
    });
    setSpeaking(started);
  }

  async function onSendCode(e: FormEvent) {
    e.preventDefault();
    unlockSpeech();
    setLoginBusy(true);
    setLoginError(null);
    try {
      await requestCitizenOtp(phone);
      setOtpSent(true);
    } catch (err) {
      loginFail(err);
    } finally {
      setLoginBusy(false);
    }
  }

  async function onVerifyOtp(e: FormEvent) {
    e.preventDefault();
    unlockSpeech();
    setLoginBusy(true);
    setLoginError(null);
    try {
      await verifyCitizenOtp(phone, otp);
      setOtp("");
      setSignedIn(true);
    } catch (err) {
      loginFail(err);
    } finally {
      setLoginBusy(false);
    }
  }

  async function onLogin(e: FormEvent) {
    e.preventDefault();
    unlockSpeech();
    setLoginBusy(true);
    setLoginError(null);
    try {
      await loginCitizen(email, password);
      setPassword("");
      setSignedIn(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setLoginError("Those credentials were not accepted.");
      } else if (err instanceof ApiError && err.status === 503) {
        setLoginError("Authentication is not configured on this server.");
      } else {
        setLoginError("Could not reach the API.");
      }
    } finally {
      setLoginBusy(false);
    }
  }

  if (!signedIn) {
    return (
      <main className="shell">
        <article className="pass">
          <Brand />
          <header>
            <p className="eyebrow">Citizen</p>
            <h1>Sign in</h1>
          </header>
          <p className="muted">
            Sign in with the mobile number SETU has for your village. After you
            enter, tap Enable alerts so the next warning can also pop up on this phone.
          </p>
          {!useEmail ? (
            <form className="stack" onSubmit={(event) => void (otpSent ? onVerifyOtp(event) : onSendCode(event))}>
              <label className="field">
                <span>Mobile number</span>
                <input
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel"
                  required
                  value={phone}
                  onChange={(event) => {
                    setPhone(event.target.value);
                    setOtpSent(false);
                  }}
                />
              </label>
              {otpSent ? (
                <label className="field">
                  <span>Code from SMS</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    required
                    value={otp}
                    onChange={(event) => setOtp(event.target.value)}
                  />
                </label>
              ) : null}
              {loginError ? (
                <p className="error" role="alert">
                  {loginError}
                </p>
              ) : null}
              <button type="submit" className="primary" disabled={loginBusy || !phone.trim()}>
                {loginBusy
                  ? otpSent
                    ? "Checking…"
                    : "Sending…"
                  : otpSent
                    ? "Verify and enter"
                    : "Send code"}
              </button>
              <button
                type="button"
                className="textlink"
                onClick={() => {
                  setUseEmail(true);
                  setLoginError(null);
                }}
              >
                Use email instead
              </button>
            </form>
          ) : (
            <form className="stack" onSubmit={(event) => void onLogin(event)}>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(event) => {
                    setEmailTouched(true);
                    setEmail(event.target.value);
                  }}
                />
              </label>
              <label className="field">
                <span>Password</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              {loginError ? (
                <p className="error" role="alert">
                  {loginError}
                </p>
              ) : null}
              <button type="submit" className="primary" disabled={loginBusy}>
                {loginBusy ? "Signing in…" : "Sign in"}
              </button>
              <button
                type="button"
                className="textlink"
                onClick={() => {
                  setUseEmail(false);
                  setLoginError(null);
                }}
              >
                Use mobile number
              </button>
            </form>
          )}
        </article>
      </main>
    );
  }

  if (!delivery && !loading) {
    return (
      <main className="shell">
        <article className="pass">
        <Brand />
        <header>
          <p className="eyebrow">Citizen</p>
          <h1>No warning for your village right now</h1>
        </header>
        <p className="muted">
          When the district sends one, it will open here. You do not need to search for it.
        </p>
        {pushConfigured(cfg) && pushSupported() && pushState !== "enabled" ? (
          <button
            type="button"
            className="primary"
            disabled={pushState === "busy"}
            onClick={() => onEnableAlerts()}
          >
            {pushState === "busy" ? "Enabling…" : "Enable alerts on this phone"}
          </button>
        ) : null}
        {pushState === "enabled" ? <p className="muted">Alerts enabled on this phone.</p> : null}
        {pushState === "error" ? (
          <p className="muted" role="alert">
            {pushError ?? "Couldn't enable alerts — try again shortly."}
          </p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
        <button type="button" className="textlink" onClick={expireSession}>
          Sign out
        </button>
        </article>
      </main>
    );
  }

  if (loading || !delivery) {
    return (
      <main className="shell">
        <article className="pass">
          <Brand />
          <div className="loading">
            <p className="eyebrow">Citizen</p>
            <p className="muted">Loading alert…</p>
          </div>
        </article>
      </main>
    );
  }

  return (
    <main className={`shell ${severityClass}`}>
      <article className="pass">
      <Brand />
      <header>
        <p className="live-banner">This is a live emergency alert</p>
        {offline ? (
          <p className="notice" role="status">
            No signal. This is the copy already on this phone.
          </p>
        ) : null}
        <p className={`eyebrow eyebrow--${delivery.severity}`}>{delivery.severity}</p>
        <h1>{delivery.headline}</h1>
        {delivery.fallback_notice ? (
          <p className="notice" role="status">
            {delivery.fallback_notice}
          </p>
        ) : null}
        {delivery.simulated ? (
          <span className="badge" title="Simulated carrier — flagged in the database">
            SIM
            <span className="sr-only">. Simulated carrier — flagged in the database</span>
          </span>
        ) : null}
        {peerProvenance ? (
          <span className="badge badge--peer" title="Received via a nearby device, signature verified">
            <IconPeer />
            PEER
            <span className="sr-only">. Received via a nearby device · signature verified</span>
          </span>
        ) : null}
      </header>
      <p className="body">{delivery.body}</p>
      {speechSupported() ? (
        <button type="button" className="textlink" onClick={onReadWarning}>
          {speaking ? "Stop reading" : "Read this warning"}
        </button>
      ) : null}
      <div className="pass__perforation" aria-hidden />
      {shelter ? (
        <section className="shelter" aria-label="Nearest shelter">
          <p className="shelter__title">Nearest shelter</p>
          <p>
            {shelter.name} · {shelter.kind} · {Math.round(shelter.distance_m)} m
          </p>
          <p className="muted">{shelter.disclosure}</p>
        </section>
      ) : null}
      <p className="meta">
        {delivery.channel_code} · Delivery {delivery.delivery_id}
      </p>
      {pushConfigured(cfg) && pushSupported() && pushState !== "enabled" ? (
        <button
          type="button"
          className="textlink"
          disabled={pushState === "busy"}
          onClick={() => onEnableAlerts()}
        >
          {pushState === "busy" ? "Enabling…" : "Enable alerts on this phone"}
        </button>
      ) : null}
      {pushState === "enabled" ? <p className="muted">Alerts enabled on this phone.</p> : null}
      {pushState === "error" ? (
        <p className="muted" role="alert">
          {pushError ?? "Couldn't enable alerts — try again, or keep using this link."}
        </p>
      ) : null}
      {peerProvenance ? (
        <p className="muted">
          Received via a nearby device · signature verified. Peer relay is one hop
          {peerHops != null ? ` (${peerHops})` : ""}, not a mesh.
        </p>
      ) : null}

      {screen === "alert" ? (
        <div className="actions">
          <button
            type="button"
            className="safe"
            disabled={!labelsReady}
            onClick={() => void onSafe()}
          >
            <IconCheck />
            <span>{safeLabel ?? "…"}</span>
          </button>
          <button
            type="button"
            className="danger"
            disabled={!labelsReady}
            onClick={() => setScreen("help")}
          >
            <IconAlert />
            <span>{helpLabel ?? "…"}</span>
          </button>
          {peerEnabled && delivery.signature && delivery.effective_at ? (
            <button
              type="button"
              className="ghost share"
              onClick={() =>
                void sharePeer(
                  {
                    headline: delivery.headline,
                    body: delivery.body,
                    severity: delivery.severity,
                    alert_id: delivery.alert_id,
                    delivery_id: delivery.delivery_id,
                    effective_at: delivery.effective_at ?? new Date().toISOString(),
                    expires_at: delivery.expires_at ?? null,
                    signature: delivery.signature ?? undefined,
                  },
                  {
                    enabled: peerEnabled,
                    chunkBytes: peerChunk ?? 0,
                    serviceUuid: peerService,
                    charUuid: peerChar,
                  },
                )
                  .then((how) =>
                    setStatus(
                      how === "bluetooth"
                        ? "Shared over Bluetooth."
                        : how === "share"
                          ? "Shared a signed link. Open it on the other phone in Chrome."
                          : how === "copied"
                            ? "Copied a signed link. Paste it in Chrome on the other phone."
                            : "Could not copy a link. Open SETU on the other phone and ask them to wait — a web page cannot advertise Bluetooth.",
                    ),
                  )
                  .catch(() => setStatus("Could not share this alert."))
              }
            >
              Share with someone nearby
            </button>
          ) : null}
        </div>
      ) : null}

      {screen === "help" ? (
        <div className="stack">
          {!labelsReady ? (
            <p className="muted">Loading choices…</p>
          ) : (
            helpTypes.map((item) => (
              <button
                key={item.id}
                type="button"
                className="choice"
                onClick={() => void onHelpType(item.id)}
              >
                {IconNeed(item.id)}
                <span>{item.label}</span>
              </button>
            ))
          )}
          <button type="button" className="ghost" onClick={() => setScreen("alert")}>
            Back
          </button>
        </div>
      ) : null}

      {screen === "location" ? (
        <div className="stack">
          <p className="prompt">Share your location so responders can find you?</p>
          <p className="muted">
            Declining still files the case. It uses area-level geography instead of a point.
          </p>
          <button
            type="button"
            className="primary"
            disabled={locBusy || geoTimeout == null}
            onClick={() => void shareLocation()}
          >
            {locBusy ? "Locating…" : "Share location"}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={locBusy || !pendingType}
            onClick={() => pendingType && void sendResponse(pendingType)}
          >
            Continue without
          </button>
        </div>
      ) : null}

      {screen === "other" ? (
        <div className="stack">
          {freeTextMax !== null ? (
            <textarea
              maxLength={freeTextMax}
              placeholder="Describe what you need"
              value={otherText}
              onChange={(e) => setOtherText(e.target.value)}
            />
          ) : (
            <p className="muted">Loading form limits…</p>
          )}
          <button
            type="button"
            className="primary"
            disabled={freeTextMax === null || !otherText.trim()}
            onClick={() => void submitOther()}
          >
            Send
          </button>
          <button type="button" className="ghost" onClick={() => setScreen("help")}>
            Back
          </button>
        </div>
      ) : null}

      {status ? (
        <p className={`status${pending ? " is-pending" : ""}`}>
          {pending ? <span className="pending-chip">Pending</span> : null}
          {status}
        </p>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      <button type="button" className="textlink" onClick={expireSession}>
        Sign out
      </button>
      </article>
    </main>
  );
}
