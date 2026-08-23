/** Typed API client.
 *
 * One place holds the access token and one place attaches it, so a new screen
 * cannot accidentally call the API unauthenticated and get a confusing 401.
 *
 * Token storage: sessionStorage, not localStorage. An operations console on a
 * shared DEOC machine should not leave a credential behind for the next
 * person who opens the browser; sessionStorage dies with the tab. Access
 * tokens last 15 minutes; the refresh token lives in the same tab store so a
 * reload or a long Write session can rotate instead of dying with
 * missing_or_invalid_token.
 */

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
const ACCESS_KEY = "setu.console.access";
const REFRESH_KEY = "setu.console.refresh";
let memoryRefresh: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function opsSocketUrl(token: string): string {
  const path = `/api/v1/ws/ops?token=${encodeURIComponent(token)}`;
  if (API_BASE) {
    const u = new URL(API_BASE);
    const protocol = u.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${u.host}${path}`;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

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
  else {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
    memoryRefresh = null;
  }
}

export function setSession(access: string, refresh: string): void {
  setToken(access);
  memoryRefresh = refresh;
  sessionStorage.setItem(REFRESH_KEY, refresh);
}

function currentRefresh(): string | null {
  return memoryRefresh ?? sessionStorage.getItem(REFRESH_KEY);
}

async function rotateRefresh(): Promise<boolean> {
  const stored = currentRefresh();
  if (!stored) return false;
  if (refreshInFlight) return refreshInFlight;
  const current = stored;
  refreshInFlight = (async () => {
    const res = await fetch(apiUrl("/api/v1/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: current }),
    });
    if (!res.ok) {
      setToken(null);
      return false;
    }
    const data = (await res.json()) as LoginResponse;
    setSession(data.access_token, data.refresh_token);
    return true;
  })();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retried = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(apiUrl(path), { ...init, headers });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    if (
      res.status === 401 &&
      !retried &&
      !path.includes("/auth/") &&
      (await rotateRefresh())
    ) {
      return request<T>(path, init, true);
    }
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
  patch: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PATCH", body: body ? JSON.stringify(body) : "{}" }),
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

/** Worst first. A desk sorted by arrival time buries an Extreme under twenty
 *  Moderates, which is the opposite of what the column "How serious" is for.
 *  Declared next to the type so the two cannot drift apart. */
export const SEVERITY_RANK: Record<string, number> = {
  extreme: 4,
  severe: 3,
  moderate: 2,
  minor: 1,
};

export function bySeverityThenTime(
  a: { severity: string; effective_at: string },
  b: { severity: string; effective_at: string },
): number {
  // Unknown severity sorts last rather than as "minor" — inventing a rank for
  // a value we do not recognise is how a real Extreme could end up buried.
  const rank = (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0);
  if (rank !== 0) return rank;
  return b.effective_at.localeCompare(a.effective_at);
}

export interface AlertSummary {
  id: number;
  incident_id: number | null;
  source_id: string;
  severity: Severity | string;
  headline: string;
  lifecycle_status: string;
  effective_at: string;
  expires_at: string | null;
  is_authoritative: boolean;
  /** Area touches an admin unit we can target. Not a bounding box - a box
   *  around India also contains Kabul. */
  domestic: boolean;
}

export interface AlertDetail extends AlertSummary {
  body: string;
  lang: string;
  version_number: number;
  target_count: number;
  approval_have: number;
  approval_need: number;
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

export interface CitizenReply {
  id: number;
  channel_code: string;
  response_type: string;
  free_text: string | null;
  unit_name: string;
  received_at: string;
  assistance_case_id: number | null;
  alert_id?: number | null;
  headline?: string | null;
  severity?: string | null;
}

export interface AssistanceCase {
  id: number;
  citizen_response_id: number | null;
  priority_score: number;
  priority_factors: Record<string, unknown>;
  model_version: string;
  status: string;
  assigned_team: string | null;
  response_type: string;
  alert_id: number;
  unit_id: number;
  unit_name: string;
  free_text: string | null;
  lat: number | null;
  lon: number | null;
  channel_code?: string | null;
}

export type PublicConfig = Record<string, string | number>;

export interface IncidentSummary {
  id: number;
  label: string;
  incident_type: string;
  status: string;
  origin_source: string;
  opened_at: string;
  version_count: number;
}

export interface TimelineEvent {
  id: number;
  event_type: string;
  payload: unknown;
  actor: string | null;
  occurred_at: string;
  alert_id: number | null;
  delivery_id: number | null;
}

export interface IncidentDetail {
  id: number;
  label: string;
  incident_type: string;
  status: string;
  origin_source: string;
  opened_at: string;
  versions: Array<{
    id: number;
    version_number: number;
    severity: string;
    lifecycle_status: string;
    change_reason: string | null;
    supersedes_alert_id: number | null;
    effective_at: string | null;
    expires_at: string | null;
  }>;
}

export interface LeadTime {
  p10: number | null;
  p50: number | null;
  p90: number | null;
  coverage_pct: number;
  alerts_with_onset: number;
  alerts_total: number;
  excluded_seismic_count: number;
  exclusion_reason: string;
}

export interface GeoFeatureCollection {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: string; coordinates: unknown };
    properties: Record<string, unknown>;
  }>;
}

export interface MapPayload {
  tile_source: string;
  openfreemap_style_url: string;
  pmtiles_min_bytes?: number;
  center: [number, number];
  zoom: number;
  units: GeoFeatureCollection;
  alerts: GeoFeatureCollection;
}

export interface PreviewResponse {
  alert_id: number;
  recipient_count: number;
  estimated_population?: number | null;
  building_count?: number | null;
  units: Array<{
    unit_id: number;
    name: string;
    recipients: number;
    estimated_population?: number | null;
    building_count?: number | null;
  }>;
}

export interface Reachability {
  unit_id: number;
  name: string;
  geometry_level: number;
  estimated_population: number | null;
  registered_recipients: number;
  reached_recipients: number;
  acknowledged_recipients: number;
  unverified_recipients: number;
  recipient_reach_pct: number | null;
  population_reach_pct: number | null;
  last_dispatch_at: string | null;
}

export interface UnitRisk {
  unit_id: number;
  alert_id: number | null;
  risk_score: number | null;
  top_factors: Array<{ factor: string; value: unknown }>;
  recommended_action: string | null;
  is_bootstrap: boolean;
  disclosure: string;
}

export interface Vulnerability {
  unit_id: number;
  name: string;
  tower_count_5km: number | null;
  nearest_tower_km: number | null;
  terrain_ruggedness: number | null;
  historical_reach_pct: number | null;
  primary_factors: string[];
  recommended_fallback: string;
}

export interface SilentVillage {
  unit_id: number;
  unit_name: string;
  /** Reached on a real channel, still said nothing. */
  silent_people: number;
  quietest_minutes: number;
  runner_exists: boolean;
  /** Relay contacts registered for this village - zero means nobody to ring. */
  contacts: number;
}

export interface OpsSummary {
  targeted: number;
  delivered: number;
  acknowledged: number;
  at_risk: number;
  delivered_note: string;
  acknowledged_note: string;
  at_risk_note: string;
  silence_minutes: number;
  silent: SilentVillage[];
}

export interface OpsFeedItem {
  occurred_at: string;
  event_type: string;
  delivery_id: number;
  alert_id: number;
  headline: string;
  severity?: string;
  channel_code: string;
  simulated: boolean;
  response_type?: string | null;
  free_text?: string | null;
}

export interface AfterActionRec {
  id: string;
  recommendation: string;
  measurement: string;
  value: number;
  denominator?: number;
}

export interface AfterAction {
  incident_id: number;
  label: string;
  status: string;
  recommendations: AfterActionRec[];
}

export interface EnrollmentImport {
  total_rows: number;
  inserted: number;
  skipped: number;
  rejected: number;
  dry_run: boolean;
  preview_token: string | null;
  rows: Array<{ row_number: number; status: string; reason: string | null }>;
}

export interface RelayTask {
  id: number;
  alert_id: number;
  state: string;
  unit_id: number;
  unit_name: string;
  headline: string;
  severity: string;
  /** Who to actually ring. Null when the village has no active relay node,
   *  which is itself the thing the officer needs to know. */
  contact_name: string | null;
  contact_kind: string | null;
  /** Only sent to roles that place the call. Null for auditor and relay_node. */
  contact_phone: string | null;
  /** Every active contact for the village, dispatcher-priority order. The first
   *  entry is the same node as contact_name. Ringing one person is rarely what
   *  an unreachable village actually needs. */
  contacts?: Array<{
    id: number;
    kind: string;
    name: string;
    phone: string | null;
  }>;
}

export const endpoints = {
  login: async (email: string, password: string) => {
    const res = await api.post<LoginResponse>("/api/v1/auth/login", { email, password });
    setSession(res.access_token, res.refresh_token);
    return res;
  },
  me: () => api.get<Me>("/api/v1/auth/me"),
  publicConfig: () => api.get<PublicConfig>("/api/v1/public/config"),
  alerts: (opts?: {
    lifecycle_status?: string;
    source_id?: string;
    authoritative?: boolean;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (opts?.lifecycle_status) q.set("lifecycle_status", opts.lifecycle_status);
    if (opts?.source_id) q.set("source_id", opts.source_id);
    if (opts?.authoritative != null) q.set("authoritative", String(opts.authoritative));
    if (opts?.limit != null) q.set("limit", String(opts.limit));
    const qs = q.toString();
    return api.get<AlertSummary[]>(`/api/v1/alerts${qs ? `?${qs}` : ""}`);
  },
  alert: (id: number) => api.get<AlertDetail>(`/api/v1/alerts/${id}`),
  createAlert: (body: Record<string, unknown>) =>
    api.post<{ alert_id: number; incident_id: number; target_count: number; lifecycle_status: string }>(
      "/api/v1/alerts",
      body,
    ),
  patchAlert: (id: number, body: Record<string, unknown>) =>
    api.patch<PreviewResponse>(`/api/v1/alerts/${id}`, body),
  preview: (id: number) => api.post<PreviewResponse>(`/api/v1/alerts/${id}/preview`),
  newVersion: (id: number, body: Record<string, unknown>) =>
    api.post<{ alert_id: number; incident_id: number; version_number: number; supersedes_alert_id: number }>(
      `/api/v1/alerts/${id}/new-version`,
      body,
    ),
  validate: (id: number) => api.post<ValidateResponse>(`/api/v1/alerts/${id}/validate`),
  approve: (id: number, reason?: string) =>
    api.post<ApproveResponse>(`/api/v1/alerts/${id}/approve`, { reason: reason ?? null }),
  dispatch: (id: number) => api.post<{ alert_id: number; recipient_count: number }>(
    `/api/v1/alerts/${id}/dispatch`,
  ),
  assurance: (id: number) => api.get<AssuranceResponse>(`/api/v1/alerts/${id}/assurance`),
  alertResponses: (id: number) =>
    api.get<CitizenReply[]>(`/api/v1/alerts/${id}/responses`),
  deliveries: (id: number) =>
    api.get<DeliveryRow[]>(`/api/v1/alerts/${id}/deliveries`),
  assistance: (status = "all") =>
    api.get<AssistanceCase[]>(`/api/v1/assistance?status=${encodeURIComponent(status)}`),
  assignCase: (id: number, assigned_team: string) =>
    api.post<AssistanceCase>(`/api/v1/assistance/${id}/assign`, { assigned_team }),
  patchCase: (id: number, body: { status: string; assigned_team?: string }) =>
    api.patch<AssistanceCase>(`/api/v1/assistance/${id}`, body),
  map: () => api.get<MapPayload>("/api/v1/ops/map"),
  opsSummary: () => api.get<OpsSummary>("/api/v1/ops/summary"),
  opsFeed: () => api.get<OpsFeedItem[]>("/api/v1/ops/feed"),
  opsReplies: () => api.get<CitizenReply[]>("/api/v1/ops/replies"),
  incidents: () => api.get<IncidentSummary[]>("/api/v1/incidents"),
  incident: (id: number) => api.get<IncidentDetail>(`/api/v1/incidents/${id}`),
  timeline: (id: number) => api.get<TimelineEvent[]>(`/api/v1/incidents/${id}/timeline`),
  board: (id: number) => api.get<Record<string, unknown>>(`/api/v1/incidents/${id}/board`),
  afterAction: (id: number) => api.get<AfterAction>(`/api/v1/incidents/${id}/after-action`),
  closeIncident: (id: number) => api.post<Record<string, unknown>>(`/api/v1/incidents/${id}/close`),
  models: () => api.get<Array<Record<string, unknown>>>("/api/v1/models"),
  soundSiren: (id: number) =>
    api.post<{
      alert_id: number;
      sirens: number;
      delivery_ids: number[];
      already_sounded: boolean;
      last_sounded_at: string | null;
      cooldown_seconds: number | null;
    }>(
      `/api/v1/alerts/${id}/siren`,
    ),
  relayTasks: () => api.get<RelayTask[]>("/api/v1/relay/tasks"),
  confirmRelayTask: (id: number) => api.post<Record<string, unknown>>(`/api/v1/relay/tasks/${id}/confirm`),
  leadTime: () => api.get<LeadTime>("/api/v1/analytics/lead-time"),
  methodology: () => api.get<Record<string, unknown>>("/api/v1/methodology"),
  reachability: (id: number) => api.get<Reachability>(`/api/v1/units/${id}/reachability`),
  vulnerability: (id: number) => api.get<Vulnerability>(`/api/v1/units/${id}/vulnerability`),
  risk: (id: number) => api.get<UnitRisk>(`/api/v1/units/${id}/risk`),
  units: (q?: string) =>
    api.get<Array<{ unit_id: number; name: string; level: number }>>(
      q ? `/api/v1/units?q=${encodeURIComponent(q)}` : "/api/v1/units",
    ),
  importRecipients: async (file: File, dryRun: boolean, previewToken?: string) => {
    const token = getToken();
    const body = new FormData();
    body.append("file", file);
    const query = new URLSearchParams({ dry_run: dryRun ? "true" : "false" });
    if (previewToken) query.set("preview_token", previewToken);
    const res = await fetch(apiUrl(`/api/v1/admin/recipients/import?${query.toString()}`), {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body,
    });
    const text = await res.text();
    const parsed = text ? JSON.parse(text) : undefined;
    if (!res.ok) {
      const detail = parsed?.detail ?? parsed;
      const code =
        (typeof detail === "object" && detail && "code" in detail
          ? String((detail as Record<string, unknown>).code)
          : undefined) ?? String(res.status);
      throw new ApiError(res.status, code, detail);
    }
    return parsed as EnrollmentImport;
  },
  reportPdf: async (id: number) => {
    const token = getToken();
    const res = await fetch(apiUrl(`/api/v1/alerts/${id}/report.pdf`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, "pdf_failed", null);
    return res.blob();
  },
};
