from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["platform"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
