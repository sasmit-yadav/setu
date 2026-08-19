from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routers import (
    ack,
    alerts,
    assistance,
    auth,
    citizen,
    enrollment,
    health,
    incidents,
    public,
    receipts,
    response,
    units,
    webhooks,
)

app = FastAPI(title="SETU API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
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
app.include_router(assistance.router)
app.include_router(incidents.router)
app.include_router(enrollment.router)
app.include_router(webhooks.router)
