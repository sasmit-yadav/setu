const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const ACCESS_KEY = "setu_citizen_token";
const REFRESH_KEY = "setu_citizen_refresh";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

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
  expires_at?: string | null;
  effective_at?: string | null;
  signature?: string | null;
  lang?: string;
  source_lang?: string;
  translated?: boolean;
  fallback_notice?: string | null;
};

export type SafeZone = {
  safe_zone_id: number;
  name: string;
  kind: string;
  lat: number;
  lon: number;
  distance_m: number;
  disclosure: string;
};

export function citizenToken(): string | undefined {
  if (typeof sessionStorage !== "undefined") {
    const stored = sessionStorage.getItem(ACCESS_KEY);
    if (stored) return stored;
  }
  return import.meta.env.VITE_CITIZEN_ACCESS_TOKEN as string | undefined;
}

export function hasCitizenSession(): boolean {
  return Boolean(citizenToken());
}

export function setCitizenSession(access: string, refresh: string) {
  sessionStorage.setItem(ACCESS_KEY, access);
  sessionStorage.setItem(REFRESH_KEY, refresh);
}

export function clearCitizenSession() {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
}

function authHeaders(): Record<string, string> {
  const token = citizenToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshCitizenSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    if (typeof sessionStorage === "undefined") return false;
    const refresh = sessionStorage.getItem(REFRESH_KEY);
    if (!refresh) return false;
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      clearCitizenSession();
      return false;
    }
    const data = (await res.json()) as { access_token: string; refresh_token: string };
    setCitizenSession(data.access_token, data.refresh_token);
    return true;
  })();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers: Record<string, string> = {
    ...authHeaders(),
    ...((init.headers as Record<string, string> | undefined) ?? {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401 && retry && !path.includes("/auth/")) {
    if (await refreshCitizenSession()) {
      return apiFetch(path, init, false);
    }
  }
  return res;
}

function idempotencyKey(prefix: string) {
  return `${prefix}-${crypto.randomUUID()}`;
}

async function parseJson(res: Response) {
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json();
}

export async function loginCitizen(email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = (await parseJson(res)) as {
    access_token: string;
    refresh_token: string;
    role: string;
    email: string;
  };
  setCitizenSession(data.access_token, data.refresh_token);
  return data;
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
  const res = await apiFetch(`/api/v1/citizen/deliveries/${deliveryId}`);
  return parseJson(res);
}

export async function fetchSafeZone(deliveryId: number): Promise<SafeZone | null> {
  const res = await apiFetch(`/api/v1/citizen/deliveries/${deliveryId}/safe-zone`);
  if (res.status === 404) return null;
  return parseJson(res);
}

export async function postAck(deliveryId: number) {
  const res = await apiFetch("/api/v1/ack", {
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
  extra?: {
    freeText?: string;
    lat?: number;
    lon?: number;
    locationConsent?: boolean;
  },
) {
  const res = await apiFetch("/api/v1/response", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey("response"),
    },
    body: JSON.stringify({
      delivery_id: deliveryId,
      response_type: responseType,
      free_text: extra?.freeText ?? null,
      lat: extra?.lat ?? null,
      lon: extra?.lon ?? null,
      location_consent: extra?.locationConsent ?? false,
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

export async function postPeerReceipt(payload: {
  delivery_id: number;
  alert_id: number;
  headline: string;
  severity: string;
  effective_at: string;
  signature: string;
}) {
  const res = await fetch(`${API_BASE}/api/v1/relay/receipt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(res);
}

export async function registerDevice(pushToken: string): Promise<{ recipient_id: number; unit_id: number }> {
  const res = await apiFetch("/api/v1/citizen/device", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ push_token: pushToken }),
  });
  return parseJson(res);
}

export function apiBase() {
  return API_BASE;
}
