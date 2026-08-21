from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routers import (
    ack,
    alerts,
    analytics,
    assistance,
    auth,
    citizen,
    enrollment,
    health,
    incidents,
    methodology,
    models,
    ops,
    public,
    receipts,
    relay,
    reports,
    response,
    units,
    webhooks,
    ws,
)

app = FastAPI(title="SETU API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(citizen.router)
app.include_router(alerts.router)
app.include_router(units.router)
app.include_router(response.router)
app.include_router(ack.router)
app.include_router(receipts.router)
app.include_router(relay.router)
app.include_router(assistance.router)
app.include_router(incidents.router)
app.include_router(enrollment.router)
app.include_router(webhooks.router)
app.include_router(ops.router)
app.include_router(analytics.router)
app.include_router(methodology.router)
app.include_router(models.router)
app.include_router(reports.router)
app.include_router(ws.router)
