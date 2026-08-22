import { verifyAlertSignature } from "./verify";

const CHANNEL = "setu-peer-relay";
const PEER_QUERY = "peer";

export type PeerPayload = {
  headline: string;
  body: string;
  severity: string;
  alert_id: number;
  delivery_id: number;
  effective_at: string;
  expires_at: string | null;
  signature?: string;
};

type PeerCfg = {
  enabled: boolean;
  chunkBytes: number;
  serviceUuid: string;
  charUuid: string;
};

function encoder() {
  return new TextEncoder();
}

function chunkBytes(payload: string, size: number): Uint8Array[] {
  const bytes = encoder().encode(payload);
  if (size <= 0) return [bytes];
  const out: Uint8Array[] = [];
  for (let offset = 0; offset < bytes.length; offset += size) {
    out.push(bytes.slice(offset, offset + size));
  }
  return out;
}

function toB64Url(json: string): string {
  const bytes = encoder().encode(json);
  let bin = "";
  for (const byte of bytes) bin += String.fromCharCode(byte);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromB64Url(raw: string): string {
  const pad = raw + "=".repeat((4 - (raw.length % 4)) % 4);
  const b64 = pad.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

export function peerShareUrl(payload: PeerPayload): string {
  const url = new URL(window.location.href);
  url.searchParams.delete("delivery_id");
  url.searchParams.set(PEER_QUERY, toB64Url(JSON.stringify(payload)));
  return url.toString();
}

export function readPeerFromUrl(): PeerPayload | null {
  const raw = new URLSearchParams(window.location.search).get(PEER_QUERY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(fromB64Url(raw)) as PeerPayload;
    if (!parsed.headline || !parsed.delivery_id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function stripPeerFromUrl(): void {
  const url = new URL(window.location.href);
  if (!url.searchParams.has(PEER_QUERY)) return;
  url.searchParams.delete(PEER_QUERY);
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

async function writeGatt(payload: string, cfg: PeerCfg): Promise<boolean> {
  if (!cfg.serviceUuid || !cfg.charUuid) return false;
  const nav = navigator as Navigator & {
    bluetooth?: {
      requestDevice: (options: {
        filters: Array<{ services: string[] }>;
        optionalServices?: string[];
      }) => Promise<{
        gatt?: {
          connect: () => Promise<{
            getPrimaryService: (uuid: string) => Promise<{
              getCharacteristic: (uuid: string) => Promise<{
                writeValueWithResponse: (value: BufferSource) => Promise<void>;
              }>;
            }>;
          }>;
        };
      }>;
    };
  };
  if (!nav.bluetooth) return false;
  const device = await nav.bluetooth.requestDevice({
    filters: [{ services: [cfg.serviceUuid] }],
    optionalServices: [cfg.serviceUuid],
  });
  const server = await device.gatt?.connect();
  if (!server) return false;
  const service = await server.getPrimaryService(cfg.serviceUuid);
  const characteristic = await service.getCharacteristic(cfg.charUuid);
  for (const chunk of chunkBytes(payload, cfg.chunkBytes)) {
    const buf = new ArrayBuffer(chunk.byteLength);
    new Uint8Array(buf).set(chunk);
    await characteristic.writeValueWithResponse(buf);
  }
  return true;
}

async function handOffLink(url: string): Promise<"share" | "copied" | "queued"> {
  const shareData = {
    title: "SETU warning",
    text: "Signed one-hop copy. Verify on this phone — not a mesh.",
    url,
  };
  try {
    if (typeof navigator.share === "function" && navigator.canShare?.(shareData)) {
      await navigator.share(shareData);
      return "share";
    }
  } catch {
    /* user cancelled or unsupported */
  }
  try {
    await navigator.clipboard.writeText(url);
    return "copied";
  } catch {
    return "queued";
  }
}

export async function sharePeer(payload: PeerPayload, cfg: PeerCfg): Promise<string> {
  if (!cfg.enabled) {
    throw new Error("peer_relay_disabled");
  }
  const body = JSON.stringify(payload);
  let gatt = false;
  try {
    gatt = await writeGatt(body, cfg);
  } catch {
    gatt = false;
  }
  const channel = new BroadcastChannel(CHANNEL);
  channel.postMessage(payload);
  channel.close();
  const key = `setu.peer.${payload.delivery_id}`;
  localStorage.setItem(key, body);
  if (gatt) return "bluetooth";
  return handOffLink(peerShareUrl(payload));
}

export async function acceptPeerPayload(
  payload: PeerPayload,
): Promise<boolean> {
  return verifyAlertSignature(
    {
      alert_id: payload.alert_id,
      delivery_id: payload.delivery_id,
      headline: payload.headline,
      severity: payload.severity,
      effective_at: payload.effective_at,
    },
    payload.signature,
  );
}

export function listenPeer(onPayload: (payload: PeerPayload) => void): () => void {
  const channel = new BroadcastChannel(CHANNEL);
  channel.onmessage = (event) => {
    const payload = event.data as PeerPayload;
    void (async () => {
      const ok = await acceptPeerPayload(payload);
      if (!ok) {
        console.warn("peer payload discarded: signature failed");
        return;
      }
      onPayload(payload);
    })();
  };
  return () => channel.close();
}
