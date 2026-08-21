from __future__ import annotations

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.asyncio import Redis

from services.api.deps import get_conn, get_redis
from services.delivery.assurance import record
from services.delivery.channels.human_relay import confirm_relay_from_dtmf
from services.delivery.lookup import by_provider_ref
from services.delivery.webhook_verify import verify_twilio_form
from services.enrollment.sms_keyword import SmsKeywordError, handle_inbound
from services.ml.translate import lang_for_unit, resolve_alert_text
from services.response.citizen_response import record_from_dtmf

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/sms-inbound")
async def sms_inbound(
    request: Request,
    conn=Depends(get_conn),
    redis: Redis = Depends(get_redis),
) -> Response:
    try:
        form = await verify_twilio_form(request)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid_signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    from_number = form.get("From", "")
    body = form.get("Body", "")
    try:
        result = await handle_inbound(conn, redis, from_number=from_number, body=body)
    except SmsKeywordError as exc:
        raise HTTPException(status_code=422, detail={"error": exc.code, "message": exc.message}) from exc
    return Response(content=result.reply_text, media_type="text/plain")


@router.post("/sms-status")
async def sms_status(request: Request, conn=Depends(get_conn)) -> Response:
    try:
        form = await verify_twilio_form(request)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid_signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    provider_ref = form.get("MessageSid") or form.get("SmsSid")
    status = form.get("MessageStatus", "")
    if not provider_ref:
        return Response(status_code=204)
    delivery_id = await by_provider_ref(conn, provider_ref)
    if delivery_id is None:
        return Response(status_code=204)
    if status == "delivered":
        await record(
            conn,
            delivery_id,
            "device_delivered",
            source="twilio_sms_webhook",
            evidence_id=provider_ref,
        )
    return Response(status_code=204)


@router.post("/ivr-status")
async def ivr_status(request: Request, conn=Depends(get_conn)) -> Response:
    try:
        form = await verify_twilio_form(request)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="invalid_signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    provider_ref = form.get("CallSid")
    call_status = form.get("CallStatus", "")
    digits = form.get("Digits")
    delivery_id = None
    if provider_ref:
        delivery_id = await by_provider_ref(conn, provider_ref)
    if delivery_id is None and form.get("delivery_id"):
        delivery_id = int(form["delivery_id"])
    if delivery_id is None:
        return Response(status_code=204)
    if call_status == "in-progress":
        await record(
            conn,
            delivery_id,
            "device_delivered",
            source="twilio_call_webhook",
            evidence_id=provider_ref,
        )
    if digits:
        await record_from_dtmf(conn, delivery_id, digits)
        await confirm_relay_from_dtmf(conn, delivery_id, digits)
    return Response(status_code=204)


async def _build_ivr_twiml(
    delivery_id: int,
    action: str,
    conn,
    mode: str = "",
) -> Response:
    from services.api import config_repo

    if mode == "relay":
        prompt = await config_repo.get_str(conn, "relay.prompt.confirm")
        unit_id = await conn.fetchval(
            """
            SELECT r.unit_id FROM delivery d
            JOIN recipient r ON r.id = d.recipient_id
            WHERE d.id = $1
            """,
            delivery_id,
        )
        lang = await lang_for_unit(conn, int(unit_id)) if unit_id is not None else None
    else:
        safe = await config_repo.get_str(conn, "ivr.dtmf.safe")
        need_help = await config_repo.get_str(conn, "ivr.dtmf.need_help")
        prompt_template = await config_repo.get_str(conn, "ivr.prompt.main")
        prompt = prompt_template.format(safe=safe, need_help=need_help)
        lang = await conn.fetchval(
            """
            SELECT r.preferred_lang FROM delivery d
            JOIN recipient r ON r.id = d.recipient_id
            WHERE d.id = $1
            """,
            delivery_id,
        )
    alert_id = await conn.fetchval("SELECT alert_id FROM delivery WHERE id = $1", delivery_id)
    if alert_id is not None:
        resolved = await resolve_alert_text(conn, int(alert_id), str(lang) if lang else None)
        prompt = f"{resolved.headline}. {resolved.body}. {prompt}"
    gather_digits = await config_repo.get_int(conn, "ivr.gather_digits")
    gather_timeout = await config_repo.get_int(conn, "ivr.gather_timeout_s")
    callback = action or ""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather numDigits="{gather_digits}" timeout="{gather_timeout}" action="{escape(callback, {'"': "&quot;"})}" method="POST">
    <Say>{escape(prompt)}</Say>
  </Gather>
</Response>"""
    return Response(content=xml, media_type="application/xml")


# Twilio fetches TwiML with GET or POST depending on how the call was created,
# so both must be served. Registered as two routes over one shared builder
# rather than one api_route(methods=[...]) — FastAPI derives an operation_id
# per (function, method) pair, so a single multi-method handler always collides
# with itself and emits a duplicate-operation-id warning into the OpenAPI spec.
@router.get("/ivr-twiml", operation_id="ivr_twiml_get")
async def ivr_twiml_get(
    delivery_id: int,
    action: str = "",
    mode: str = "",
    conn=Depends(get_conn),
) -> Response:
    return await _build_ivr_twiml(delivery_id, action, conn, mode=mode)


@router.post("/ivr-twiml", operation_id="ivr_twiml_post")
async def ivr_twiml_post(
    delivery_id: int,
    action: str = "",
    mode: str = "",
    conn=Depends(get_conn),
) -> Response:
    return await _build_ivr_twiml(delivery_id, action, conn, mode=mode)
