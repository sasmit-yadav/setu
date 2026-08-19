/** Typed API client.
 *
 * One place holds the access token and one place attaches it, so a new screen
 * cannot accidentally call the API unauthenticated and get a confusing 401.
 *
 * Token storage: sessionStorage, not localStorage. An operations console on a
 * shared DEOC machine should not leave a credential behind for the next
 * person who opens the browser; sessionStorage dies with the tab. The refresh
 * token is deliberately NOT persisted at all — losing it on reload costs one
 * login, and persisting a long-lived revocable credential in a place XSS can
 * read is a worse trade on a system that can order an evacuation.
 */

const ACCESS_KEY = "setu.console.access";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly detail: unknown,
  ) {
    super(`${status} ${code}`);
  }
}

export function getToken(): string | null {
  return sessionStorage.getItem(ACCESS_KEY);
}

export function setToken(token: string | null): void {
  if (token) sessionStorage.setItem(ACCESS_KEY, token);
  else sessionStorage.removeItem(ACCESS_KEY);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(path, { ...init, headers });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    // The API's error contract (Part 10) is {error, code, ...} inside `detail`.
    // Surfacing `code` matters: the UI distinguishes "quality gate blocked"
    // from "approvals short" from "not your district", and each has a
    // different, specific thing for the officer to do about it.
    const detail = body?.detail ?? body;
    const code =
      (typeof detail === "object" && detail && "code" in detail
        ? String((detail as Record<string, unknown>).code)
        : undefined) ?? String(res.status);
    throw new ApiError(res.status, code, detail);
  }
  return body as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : "{}" }),
};

// ── shapes returned by the API, mirrored from services/api/schemas.py ──

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  role: string;
  email: string;
}

export interface Me {
  user_id: number;
  email: string;
  role: string;
  unit_scope_id: number | null;
}

export type Severity = "extreme" | "severe" | "moderate" | "minor";

export interface AlertSummary {
  id: number;
  incident_id: number | null;
  source_id: string;
  severity: Severity;
  headline: string;
  lifecycle_status: string;
  effective_at: string;
  expires_at: string | null;
}

export interface AlertDetail extends AlertSummary {
  body: string;
  lang: string;
  version_number: number;
  target_count: number;
}

export interface RuleResult {
  rule_id: string;
  status: "pass" | "fail" | "warn";
  message: string | null;
}

export interface ValidateResponse {
  alert_id: number;
  results: RuleResult[];
  blocked: boolean;
}

export interface ApproveResponse {
  alert_id: number;
  have: number;
  need: number;
}

/** One rung of the B8 ladder. `status` is the whole point:
 *  recorded | pending | not_applicable — three DIFFERENT facts. */
export interface Rung {
  tier: "provider_accept" | "device_delivered" | "opened" | "acknowledgement";
  status: "recorded" | "pending" | "not_applicable";
  event_type: string;
  occurred_at?: string;
  source?: string;
  evidence_id?: string | null;
  reason?: string | null;
}

export interface DeliveryAssurance {
  delivery_id: number;
  channel_code: string;
  simulated: boolean;
  state: string;
  assurance_level: number;
  rungs: Rung[];
}

export interface AssuranceResponse {
  alert_id: number;
  deliveries: DeliveryAssurance[];
}

export interface DeliveryRow {
  id: number;
  recipient_id: number;
  channel_code: string;
  state: string;
  simulated: boolean;
  assurance_level: number;
}

export const endpoints = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>("/api/v1/auth/login", { email, password }),
  me: () => api.get<Me>("/api/v1/auth/me"),
  alerts: (limit = 50) => api.get<AlertSummary[]>(`/api/v1/alerts?limit=${limit}`),
  alert: (id: number) => api.get<AlertDetail>(`/api/v1/alerts/${id}`),
  validate: (id: number) => api.post<ValidateResponse>(`/api/v1/alerts/${id}/validate`),
  approve: (id: number, reason?: string) =>
    api.post<ApproveResponse>(`/api/v1/alerts/${id}/approve`, { reason: reason ?? null }),
  dispatch: (id: number) => api.post<{ alert_id: number; recipient_count: number }>(
    `/api/v1/alerts/${id}/dispatch`,
  ),
  assurance: (id: number) => api.get<AssuranceResponse>(`/api/v1/alerts/${id}/assurance`),
  deliveries: (id: number, limit = 200) =>
    api.get<DeliveryRow[]>(`/api/v1/alerts/${id}/deliveries?limit=${limit}`),
};
