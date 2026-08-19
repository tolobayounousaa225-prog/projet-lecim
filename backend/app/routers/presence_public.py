"""Nombre de visiteurs actuellement en ligne sur la vitrine — public, anonyme,
aucun compte requis. Voir presence.py pour le mécanisme de suivi."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import presence
from ..rate_limit import rate_limiter

router = APIRouter(prefix="/api/presence", tags=["presence"])


class HeartbeatIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)


@router.post("/heartbeat", dependencies=[Depends(rate_limiter("presence-heartbeat", 20, 60))])
def presence_heartbeat(payload: HeartbeatIn):
    count = presence.heartbeat(payload.session_id)
    return {"count": count}


@router.get("/count")
def presence_count():
    return {"count": presence.count_active()}
