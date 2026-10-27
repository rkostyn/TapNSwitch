"""Live TV snapshot — the scoring iPad publishes, the TV just reads."""
from fastapi import APIRouter, Depends

from app.dependencies import get_current_user

router = APIRouter(tags=["Display"])

_snapshot: dict | None = None


@router.get("/tv/snapshot")
async def get_tv_snapshot():
    return _snapshot


@router.put("/tv/snapshot")
async def put_tv_snapshot(
    body: dict,
    _: str = Depends(get_current_user),
):
    global _snapshot
    _snapshot = body
    return _snapshot
