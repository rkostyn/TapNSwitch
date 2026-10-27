from fastapi import APIRouter, Depends, HTTPException

from app.db.mongo import MongoClient
from app.dependencies import get_current_user, get_mongo_client
from app.logger import get_logger
from app.models.event import Event
from app.models.lane import ArenaAssign, LaneBoard
from app.repositories.event_repository import EventRepository
from app.services.lanes import ArenaOccupiedError, assign_event_arenas, build_lane_board

logger = get_logger(__name__)

router = APIRouter(tags=["Lanes"])


@router.get("/lanes", response_model=LaneBoard)
async def get_lane_board(
    _: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    return await build_lane_board(repo)


@router.put("/event/{event_id}/arenas", response_model=Event)
async def set_event_arenas(
    event_id: str,
    body: ArenaAssign,
    _: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    event = await repo.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.is_finished:
        raise HTTPException(status_code=423, detail="Event is finished")
    try:
        updated = await assign_event_arenas(repo, event, body.arena_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ArenaOccupiedError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "arena_id": exc.arena_id,
                "event_id": exc.event.event_id,
                "event_name": exc.event.event_name,
            },
        ) from exc
    logger.info("Event %s assigned to arenas %s", event_id, updated.arena_ids)
    return updated
