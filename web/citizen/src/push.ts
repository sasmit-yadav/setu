import type { PublicConfig } from "./api";
import { registerDevice } from "./api";

/** Firebase web config comes entirely from the public /config endpoint — never
 * from a build-time env var — because it's the one piece of Rule-1 config
 * that also has to reach the browser at runtime, not just the server. */
export function pushConfigured(cfg: PublicConfig | null): boolean {
  return (
    typeof cfg?.["firebase.api_key"] === "string" &&
    typeof cfg?.["firebase.project_id"] === "string" &&
    typeof cfg?.["firebase.messaging_sender_id"] === "string" &&
    typeof cfg?.["firebase.app_id"] === "string" &&
    typeof cfg?.["firebase.vapid_public_key"] === "string" &&
    cfg["firebase.vapid_public_key"].length > 0
  );
}

export function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export type EnablePushResult =
  | { ok: true; recipientId: number }
  | { ok: false; reason: "not_supported" | "not_configured" | "permission_denied" | "no_token" | string };

/** Requests notification permission, gets a real FCM token bound to our own
 * service worker (sw.ts — no separate firebase-messaging-sw.js: the existing
 * `push` handler there already parses the data-only payload FcmAdapter sends),
 * and registers it against the citizen's unit-scoped recipient row. */
export async function enablePush(cfg: PublicConfig | null): Promise<EnablePushResult> {
  if (!pushSupported()) return { ok: false, reason: "not_supported" };
  if (!pushConfigured(cfg)) return { ok: false, reason: "not_configured" };

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { ok: false, reason: "permission_denied" };

  const { initializeApp, getApps } = await import("firebase/app");
  const { getMessaging, getToken } = await import("firebase/messaging");

  const firebaseConfig = {
    apiKey: cfg!["firebase.api_key"] as string,
    projectId: cfg!["firebase.project_id"] as string,
    messagingSenderId: cfg!["firebase.messaging_sender_id"] as string,
    appId: cfg!["firebase.app_id"] as string,
  };
  const app = getApps()[0] ?? initializeApp(firebaseConfig);
  const messaging = getMessaging(app);
  const registration = await navigator.serviceWorker.ready;

  const token = await getToken(messaging, {
    vapidKey: cfg!["firebase.vapid_public_key"] as string,
    serviceWorkerRegistration: registration,
  });
  if (!token) return { ok: false, reason: "no_token" };

  const result = await registerDevice(token);
  return { ok: true, recipientId: result.recipient_id };
}
