from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RuleResultOut(BaseModel):
    rule_id: str
    status: str
    message: str | None = None


class ValidateResponse(BaseModel):
    alert_id: int
    results: list[RuleResultOut]
    blocked: bool


class ApproveRequest(BaseModel):
    """The approver is NOT a field here, deliberately.

    This model used to carry `approver_id: int`, which meant any caller could
    approve as any officer and F3's Four-Eyes quorum was bypassable by typing
    a different integer. Identity now comes from the authenticated principal
    (services/api/rbac.current_principal). The field is intentionally absent
    rather than optional-and-ignored, so a client that still sends it gets a
    422 instead of silently having it discarded.
    """

    model_config = {"extra": "forbid"}

    reason: str | None = None


class ApproveResponse(BaseModel):
    alert_id: int
    have: int
    need: int


class DispatchResponse(BaseModel):
    alert_id: int
    recipient_count: int


class ReachabilityOut(BaseModel):
    unit_id: int
    name: str
    geometry_level: int
    estimated_population: int | None
    registered_recipients: int
    reached_recipients: int
    acknowledged_recipients: int
    unverified_recipients: int
    recipient_reach_pct: float | None
    population_reach_pct: float | None
    last_dispatch_at: str | None


class VulnerabilityOut(BaseModel):
    unit_id: int
    name: str
    tower_count_5km: float | None
    nearest_tower_km: float | None
    terrain_ruggedness: float | None
    historical_reach_pct: float | None
    primary_factors: list[str]
    recommended_fallback: str


class NewVersionRequest(BaseModel):
    change_reason: str = Field(min_length=1)
    severity: str | None = None
    headline: str | None = None
    body: str | None = None
    expires_at: datetime | None = None


class NewVersionResponse(BaseModel):
    alert_id: int
    incident_id: int
    version_number: int
    supersedes_alert_id: int


class CitizenResponseRequest(BaseModel):
    delivery_id: int
    response_type: str
    free_text: str | None = None
    lat: float | None = None
    lon: float | None = None
    location_consent: bool = False
    submitted_at: datetime | None = None


class CitizenResponseOut(BaseModel):
    citizen_response_id: int
    response_type: str
    assistance_case_id: int | None = None
    duplicate: bool = False


class AssistanceCaseOut(BaseModel):
    model_config = {"protected_namespaces": ()}

    id: int
    citizen_response_id: int | None = None
    priority_score: float
    priority_factors: dict
    model_version: str
    status: str
    assigned_team: str | None = None
    response_type: str
    alert_id: int
    unit_id: int
    unit_name: str
    free_text: str | None = None
    lat: float | None = None
    lon: float | None = None
    channel_code: str | None = None


class AssistanceSummaryRow(BaseModel):
    unit_id: int
    unit_name: str
    open_count: int


class AssignCaseRequest(BaseModel):
    model_config = {"extra": "forbid"}

    assigned_team: str = Field(min_length=1)


class PatchCaseRequest(BaseModel):
    model_config = {"extra": "forbid"}

    status: str = Field(min_length=1)
    assigned_team: str | None = None


class PatchAlertRequest(BaseModel):
    model_config = {"extra": "forbid"}

    expires_at: datetime | None = None
    headline: str | None = None
    body: str | None = None
    severity: str | None = None


class TimelineEventOut(BaseModel):
    id: int
    event_type: str
    payload: dict | list | str | None
    actor: str | None
    occurred_at: str
    alert_id: int | None = None
    delivery_id: int | None = None


class IncidentSummaryOut(BaseModel):
    id: int
    label: str
    incident_type: str
    status: str
    origin_source: str
    opened_at: str
    version_count: int


class IncidentDetailOut(BaseModel):
    id: int
    label: str
    incident_type: str
    status: str
    origin_source: str
    opened_at: str
    versions: list[dict]


class AckRequest(BaseModel):
    delivery_id: int


class AckResponse(BaseModel):
    delivery_id: int
    duplicate: bool


class DeviceRegisterRequest(BaseModel):
    push_token: str


class DeviceRegisterResponse(BaseModel):
    recipient_id: int
    unit_id: int


class ReceiptRequest(BaseModel):
    receipt_nonce: str
    event_type: str = "device_delivered"


class ReceiptResponse(BaseModel):
    delivery_id: int
    recorded: bool


class AssuranceRungOut(BaseModel):
    tier: str
    status: str
    event_type: str | None = None
    occurred_at: str | None = None
    source: str | None = None
    evidence_id: str | None = None
    reason: str | None = None


class DeliveryAssuranceOut(BaseModel):
    delivery_id: int
    channel_code: str
    simulated: bool
    state: str
    assurance_level: int
    rungs: list[AssuranceRungOut]


class AssuranceOut(BaseModel):
    alert_id: int
    deliveries: list[DeliveryAssuranceOut]


class DeliveryRowOut(BaseModel):
    id: int
    recipient_id: int
    channel_code: str
    state: str
    simulated: bool
    assurance_level: int


class CitizenReplyOut(BaseModel):
    id: int
    channel_code: str
    response_type: str
    free_text: str | None
    unit_name: str
    received_at: str
    assistance_case_id: int | None
    alert_id: int | None = None
    headline: str | None = None
    severity: str | None = None


class UnitRiskOut(BaseModel):
    unit_id: int
    alert_id: int | None
    risk_score: float | None
    top_factors: list[dict]
    recommended_action: str | None
    is_bootstrap: bool
    disclosure: str


class CreateAlertRequest(BaseModel):
    severity: str
    headline: str = Field(min_length=1)
    body: str = Field(min_length=1)
    lang: str = Field(min_length=2, max_length=8)
    unit_ids: list[int] | None = None
    geojson: dict | None = None
    point_lon: float | None = None
    point_lat: float | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    estimated_onset_at: datetime | None = None


class CreateAlertResponse(BaseModel):
    alert_id: int
    incident_id: int
    target_count: int
    lifecycle_status: str


class AlertSummaryOut(BaseModel):
    id: int
    incident_id: int | None
    source_id: str
    severity: str
    headline: str
    lifecycle_status: str
    effective_at: str
    expires_at: str | None
    is_authoritative: bool = False
    # True when the alert area touches an admin unit we could actually target.
    # Not a bounding box: a rectangle around India also contains Kabul, so a
    # box test reports foreign earthquakes as domestic.
    domestic: bool = False


class AlertDetailOut(BaseModel):
    id: int
    incident_id: int | None
    source_id: str
    severity: str
    headline: str
    body: str
    lang: str
    lifecycle_status: str
    version_number: int
    effective_at: str
    expires_at: str | None
    target_count: int
    is_authoritative: bool = False
    approval_have: int = 0
    approval_need: int = 1


class PreviewResponse(BaseModel):
    alert_id: int
    recipient_count: int
    estimated_population: int | None = None
    building_count: int | None = None
    units: list[dict]


class CsvImportResponse(BaseModel):
    total_rows: int
    inserted: int
    skipped: int
    rejected: int
    dry_run: bool
    rows: list[dict]
