import { StrictMode, useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchDelivery,
  fetchPublicConfig,
  fetchSigningKey,
  postAck,
  postResponse,
  type CitizenDelivery,
} from "./api";
import { setVerifyKey } from "./verify";
import "./styles.css";

type Screen = "alert" | "help" | "other";

const HELP_TYPES = [
  { id: "trapped", label: "I am trapped" },
  { id: "medical", label: "Medical help" },
  { id: "unable_to_evacuate", label: "Cannot evacuate" },
  { id: "other", label: "Something else" },
];

function deliveryFromUrl(): number | null {
  const raw = new URLSearchParams(window.location.search).get("delivery_id");
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export default function App() {
  const [deliveryId, setDeliveryId] = useState<number | null>(deliveryFromUrl);
  const [manualId, setManualId] = useState("");
  const [delivery, setDelivery] = useState<CitizenDelivery | null>(null);
  const [screen, setScreen] = useState<Screen>("alert");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [freeTextMax, setFreeTextMax] = useState<number | null>(null);
  const [otherText, setOtherText] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const cfg = await fetchPublicConfig();
        const max = cfg["response.free_text_max_chars"];
        if (typeof max === "number") setFreeTextMax(max);
        const envKey = import.meta.env.VITE_ALERT_SIGNING_PUBKEY_B64 as string | undefined;
        const key = envKey && envKey.length > 10 ? envKey : await fetchSigningKey();
        setVerifyKey(key);
      } catch {
        return;
      }
    })();
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
      setError(e instanceof Error ? e.message : "Failed to load alert");
      setDelivery(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (deliveryId !== null) void loadDelivery(deliveryId);
  }, [deliveryId, loadDelivery]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "setu:delivery" && event.data.deliveryId) {
        void loadDelivery(Number(event.data.deliveryId));
      }
    };
    navigator.serviceWorker?.addEventListener("message", handler);
    return () => navigator.serviceWorker?.removeEventListener("message", handler);
  }, [loadDelivery]);

  const severityClass = useMemo(() => {
    if (!delivery) return "severity-minor";
    return `severity-${delivery.severity}`;
  }, [delivery]);

  async function onSafe() {
    if (!deliveryId) return;
    setStatus("Sending…");
    try {
      await postAck(deliveryId);
      await postResponse(deliveryId, "safe");
      setStatus("Marked safe. Help is on the way if others need it.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed");
    }
  }

  async function onHelpType(type: string) {
    if (!deliveryId) return;
    if (type === "other") {
      setScreen("other");
      return;
    }
    setStatus("Sending…");
    try {
      await postAck(deliveryId);
      await postResponse(deliveryId, type);
      setStatus("Help request sent.");
      setScreen("alert");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed");
    }
  }

  async function submitOther() {
    if (!deliveryId || !otherText.trim()) return;
    setStatus("Sending…");
    try {
      await postAck(deliveryId);
      await postResponse(deliveryId, "other", otherText.trim());
      setStatus("Help request sent.");
      setScreen("alert");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Failed");
    }
  }

  if (!delivery && !loading) {
    return (
      <main className="shell">
        <header>
          <p className="eyebrow">SETU Citizen</p>
          <h1>Load an alert</h1>
        </header>
        <p className="muted">Enter a delivery ID from a notification or test dispatch.</p>
        <form
          className="manual"
          onSubmit={(e) => {
            e.preventDefault();
            const id = Number(manualId);
            if (Number.isFinite(id)) void loadDelivery(id);
          }}
        >
          <input
            inputMode="numeric"
            placeholder="Delivery ID"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
          />
          <button type="submit">Open</button>
        </form>
        {error ? <p className="error">{error}</p> : null}
      </main>
    );
  }

  if (loading || !delivery) {
    return (
      <main className="shell">
        <p className="muted">Loading alert…</p>
      </main>
    );
  }

  return (
    <main className={`shell ${severityClass}`}>
      <header>
        <p className="eyebrow">{delivery.severity.toUpperCase()}</p>
        <h1>{delivery.headline}</h1>
        {delivery.simulated ? <span className="badge">SIM</span> : null}
      </header>
      <p className="body">{delivery.body}</p>
      <p className="muted">
        Channel {delivery.channel_code} · Delivery #{delivery.delivery_id}
      </p>

      {screen === "alert" ? (
        <div className="actions">
          <button type="button" className="primary safe" onClick={() => void onSafe()}>
            I&apos;m safe
          </button>
          <button type="button" className="danger" onClick={() => setScreen("help")}>
            I need help
          </button>
        </div>
      ) : null}

      {screen === "help" ? (
        <div className="stack">
          {HELP_TYPES.map((item) => (
            <button key={item.id} type="button" className="choice" onClick={() => void onHelpType(item.id)}>
              {item.label}
            </button>
          ))}
          <button type="button" className="ghost" onClick={() => setScreen("alert")}>
            Back
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
            disabled={freeTextMax === null}
            onClick={() => void submitOther()}
          >
            Send
          </button>
          <button type="button" className="ghost" onClick={() => setScreen("help")}>
            Back
          </button>
        </div>
      ) : null}

      {status ? <p className="status">{status}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </main>
  );
}
