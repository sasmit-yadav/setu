/// <reference lib="webworker" />
import { clientsClaim } from "workbox-core";
import { ExpirationPlugin } from "workbox-expiration";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { BackgroundSyncPlugin } from "workbox-background-sync";
import { registerRoute } from "workbox-routing";
import { NetworkFirst, NetworkOnly } from "workbox-strategies";
import { apiBase, postReceipt } from "./api";

declare let self: ServiceWorkerGlobalScope;

clientsClaim();
cleanupOutdatedCaches();

// In a production build __WB_MANIFEST is the real precache list. Under
// `vite-plugin-pwa`'s dev server it is injected as `[]` — nothing is
// precached, because Vite serves the app shell itself.
//
// That distinction is load-bearing: createHandlerBoundToURL() ASSERTS that the
// URL it is given is in the precache manifest and throws synchronously if it is
// not ("...that URL is not precached"). At module top level that throw aborts
// the whole service worker with "ServiceWorker script evaluation failed", so on
// the dev server we lost every SW feature at once — the offline alert cache
// (Gate 3's unplug beat) AND the push -> receipt_nonce callback that is the
// only real device_delivered signal for FCM (§8.3). Both looked like separate
// problems; they were this one line.
//
// So the navigation fallback is registered only when the shell is actually
// precached. Guarding the call, rather than removing it, keeps production
// behaviour identical.
const manifest = self.__WB_MANIFEST;
precacheAndRoute(manifest);

const APP_SHELL = "/index.html";
const shellIsPrecached = Array.isArray(manifest)
  && manifest.some((entry) => {
    const url = typeof entry === "string" ? entry : entry?.url;
    return url === APP_SHELL || url === "index.html";
  });

if (shellIsPrecached) {
  const appShell = createHandlerBoundToURL(APP_SHELL);
  registerRoute(({ request }) => request.mode === "navigate", appShell);
}

type PwaCfg = {
  networkTimeoutSeconds: number;
  alertCacheMaxAgeSeconds: number;
  ackRetentionMinutes: number;
  receiptRetentionMinutes: number;
};

let routesRegistered = false;

async function fetchPwaConfig(): Promise<PwaCfg> {
  const res = await fetch(`${apiBase()}/api/v1/public/config`);
  if (!res.ok) throw new Error("config_unavailable");
  const data = await res.json();
  const networkTimeoutSeconds = Number(data["pwa.network_timeout_seconds"]);
  const alertCacheMaxAgeSeconds = Number(data["pwa.alert_cache_max_age_seconds"]);
  const ackRetentionMinutes = Number(data["pwa.ack_retention_minutes"]);
  const receiptRetentionMinutes = Number(data["pwa.receipt_retention_minutes"]);
  if (
    !Number.isFinite(networkTimeoutSeconds) ||
    !Number.isFinite(alertCacheMaxAgeSeconds) ||
    !Number.isFinite(ackRetentionMinutes) ||
    !Number.isFinite(receiptRetentionMinutes)
  ) {
    throw new Error("config_incomplete");
  }
  return {
    networkTimeoutSeconds,
    alertCacheMaxAgeSeconds,
    ackRetentionMinutes,
    receiptRetentionMinutes,
  };
}

function registerApiRoutes(cfg: PwaCfg) {
  if (routesRegistered) return;
  routesRegistered = true;

  registerRoute(
    ({ url }) => url.pathname.startsWith("/api/v1/citizen/deliveries"),
    new NetworkFirst({
      cacheName: "setu-deliveries-v1",
      networkTimeoutSeconds: cfg.networkTimeoutSeconds,
      plugins: [new ExpirationPlugin({ maxAgeSeconds: cfg.alertCacheMaxAgeSeconds })],
    }),
  );

  const ackQueue = new BackgroundSyncPlugin("setu-ack-queue", {
    maxRetentionTime: cfg.ackRetentionMinutes,
  });
  registerRoute(
    ({ url, request }) => url.pathname === "/api/v1/ack" && request.method === "POST",
    new NetworkOnly({ plugins: [ackQueue] }),
    "POST",
  );

  const responseQueue = new BackgroundSyncPlugin("setu-response-queue", {
    maxRetentionTime: cfg.ackRetentionMinutes,
  });
  registerRoute(
    ({ url, request }) => url.pathname === "/api/v1/response" && request.method === "POST",
    new NetworkOnly({ plugins: [responseQueue] }),
    "POST",
  );

  const receiptQueue = new BackgroundSyncPlugin("setu-receipt-queue", {
    maxRetentionTime: cfg.receiptRetentionMinutes,
  });
  registerRoute(
    ({ url, request }) => /\/api\/v1\/deliveries\/\d+\/receipt$/.test(url.pathname) && request.method === "POST",
    new NetworkOnly({ plugins: [receiptQueue] }),
    "POST",
  );

  const relayQueue = new BackgroundSyncPlugin("setu-relay-receipt-queue", {
    maxRetentionTime: cfg.receiptRetentionMinutes,
  });
  registerRoute(
    ({ url, request }) => url.pathname === "/api/v1/relay/receipt" && request.method === "POST",
    new NetworkOnly({ plugins: [relayQueue] }),
    "POST",
  );
}

async function bootstrap() {
  const cfg = await fetchPwaConfig();
  registerApiRoutes(cfg);
}

void bootstrap();

self.addEventListener("activate", (event) => {
  event.waitUntil(bootstrap().catch(() => undefined));
});

self.addEventListener("push", (event) => {
  event.waitUntil(
    (async () => {
      if (!event.data) return;
      const data = event.data.json() as {
        headline?: string;
        body?: string;
        delivery_id?: number;
        receipt_nonce?: string;
      };
      const headline = data.headline ?? "SETU Alert";
      const body = data.body ?? "";
      await self.registration.showNotification(headline, {
        body,
        data,
        icon: "/icon-192.png",
        badge: "/icon-192.png",
        tag: "setu-alert",
        renotify: true,
        requireInteraction: true,
        vibrate: [200, 100, 200, 100, 400],
      });
      if (data.delivery_id && data.receipt_nonce) {
        try {
          await postReceipt(data.delivery_id, data.receipt_nonce, "device_delivered");
        } catch {
          undefined;
        }
      }
    })(),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data as { delivery_id?: number; receipt_nonce?: string } | undefined;
  const deliveryId = data?.delivery_id;
  event.waitUntil(
    (async () => {
      if (deliveryId && data?.receipt_nonce) {
        try {
          await postReceipt(deliveryId, data.receipt_nonce, "notification_opened");
        } catch {
          undefined;
        }
      }
      const url = deliveryId ? `/?delivery_id=${deliveryId}` : "/";
      const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of clients) {
        if ("focus" in client) {
          await client.focus();
          client.postMessage({ type: "setu:delivery", deliveryId });
          return;
        }
      }
      await self.clients.openWindow(url);
    })(),
  );
});
