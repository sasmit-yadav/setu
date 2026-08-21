import { verifyAlertSignature } from "./verify";

const CHANNEL = "setu-peer-relay";

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
  const out: Uint8Array[] = [];
  for (let offset = 0; offset < bytes.length; offset += size) {
    out.push(bytes.slice(offset, offset + size));
  }
  return out;
}

async function writeGatt(payload: string, cfg: PeerCfg): Promise<boolean> {
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
  return gatt ? "bluetooth" : "queued";
}

export function listenPeer(onPayload: (payload: PeerPayload) => void): () => void {
  const channel = new BroadcastChannel(CHANNEL);
  channel.onmessage = (event) => {
    const payload = event.data as PeerPayload;
    void (async () => {
      const ok = await verifyAlertSignature(
        {
          alert_id: payload.alert_id,
          delivery_id: payload.delivery_id,
          headline: payload.headline,
          severity: payload.severity,
          effective_at: payload.effective_at,
        },
        payload.signature,
      );
      if (!ok) {
        console.warn("peer payload discarded: signature failed");
        return;
      }
      onPayload(payload);
    })();
  };
  return () => channel.close();
}
