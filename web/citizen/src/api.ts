const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type PublicConfig = Record<string, string | number>;

export type CitizenDelivery = {
  delivery_id: number;
  alert_id: number;
  headline: string;
  body: string;
  severity: string;
  channel_code: string;
  simulated: boolean;
  lifecycle_status: string;
};

function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

async function parseJson(res: Response) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export async function fetchPublicConfig(): Promise<PublicConfig> {
  const res = await fetch(`${API_BASE}/api/v1/public/config`);
  return parseJson(res);
}

export async function fetchSigningKey(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/public/signing-key`);
  const data = await parseJson(res);
  return data.public_key_b64 as string;
}

export async function fetchDelivery(deliveryId: number): Promise<CitizenDelivery> {
  const res = await fetch(`${API_BASE}/api/v1/citizen/deliveries/${deliveryId}`);
  return parseJson(res);
}

export async function postAck(deliveryId: number) {
  const res = await fetch(`${API_BASE}/api/v1/ack`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey("ack"),
    },
    body: JSON.stringify({ delivery_id: deliveryId }),
  });
  return parseJson(res);
}

export async function postResponse(
  deliveryId: number,
  responseType: string,
  freeText?: string,
) {
  const res = await fetch(`${API_BASE}/api/v1/response`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey("response"),
    },
    body: JSON.stringify({
      delivery_id: deliveryId,
      response_type: responseType,
      free_text: freeText ?? null,
    }),
  });
  return parseJson(res);
}

export async function postReceipt(
  deliveryId: number,
  receiptNonce: string,
  eventType = "device_delivered",
) {
  const res = await fetch(`${API_BASE}/api/v1/deliveries/${deliveryId}/receipt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ receipt_nonce: receiptNonce, event_type: eventType }),
  });
  return parseJson(res);
}

export function apiBase() {
  return API_BASE;
}
