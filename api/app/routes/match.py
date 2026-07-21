from fastapi import APIRouter, Depends, Header, HTTPException
from app.db.mongo import MongoClient
from app.dependencies import get_mongo_client, get_current_user, rate_limit
from app.repositories.match_repository import MatchRepository
from app.repositories.event_repository import EventRepository
from app.repositories.throw_repository import ThrowRepository
from app.repositories.venue_repository import VenueRepository
from app.models.match import Match, MatchCreate, MatchRoundsUpdate, MatchArenaUpdate
from app.models.throw import ThrowsGet
from app.services.tournament import compute_match_winner
from app.services.match_results import update_match_winner
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/match", tags=["Matches"])


@router.post("", response_model=Match)
async def create_match(
    body: MatchCreate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Creating match for event %s", body.event_id)
    if body.event_id:
        event_repo = EventRepository(mongo_client)
        event = await event_repo.get_event(body.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.is_finished:
            raise HTTPException(status_code=423, detail="Event is finished")
        if event.is_locked and event.locked_by != current_user:
            raise HTTPException(status_code=423, detail="Event is locked by another user")
    repo = MatchRepository(mongo_client)
    return await repo.create_match(body)


@router.get("/event/{event_id}", response_model=list[Match], dependencies=[Depends(rate_limit(60))])
async def get_matches_by_event(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching matches for event %s", event_id)
    repo = MatchRepository(mongo_client)
    return await repo.get_matches_by_event(event_id)


@router.get("/{match_id}", response_model=Match, dependencies=[Depends(rate_limit(60))])
async def get_match(
    match_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching match %s", match_id)
    repo = MatchRepository(mongo_client)
    result = await repo.get_match(match_id)
    if not result:
        raise HTTPException(status_code=404, detail="Match not found")
    return result


@router.delete("/{match_id}", status_code=204)
async def delete_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    if not await repo.delete_match(match_id):
        raise HTTPException(status_code=404, detail="Match not found")


@router.post("/{match_id}/finish", response_model=Match)
async def finish_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if existing.is_finished:
        raise HTTPException(status_code=423, detail="Match is already finished")

    throw_repo = ThrowRepository(mongo_client)
    throws = await throw_repo.get_throws_by_criteria(ThrowsGet(match_id=match_id))
    winner = compute_match_winner(existing.player_1_id, existing.player_2_id, throws)
    if existing.match_type == "bracket" and winner is None:
        raise HTTPException(status_code=409, detail="Match is tied — adjust scoring before finishing")

    result = await repo.finish_match(match_id)
    if not result:
        raise HTTPException(status_code=423, detail="Match is already finished")
    await update_match_winner(mongo_client, existing)
    return await repo.get_match(match_id)


@router.post("/{match_id}/reopen", response_model=Match)
async def reopen_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if not existing.is_finished:
        raise HTTPException(status_code=409, detail="Match is not finished")
    result = await repo.reopen_match(match_id)
    if not result:
        raise HTTPException(status_code=409, detail="Match is not finished")
    return result


@router.patch("/{match_id}/rounds", response_model=Match)
async def update_match_rounds(
    match_id: str,
    body: MatchRoundsUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if existing.is_finished:
        raise HTTPException(status_code=423, detail="Match is finished")
    return await repo.update_rounds_per_match(match_id, body.rounds_per_match)


@router.patch("/{match_id}/arena", response_model=Match)
async def update_match_arena(
    match_id: str,
    body: MatchArenaUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if existing.is_finished:
        raise HTTPException(status_code=423, detail="Match is finished")
    if body.arena_id and existing.event_id:
        event = await EventRepository(mongo_client).get_event(existing.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        allowed = set(event.arena_ids or [])
        venue_allowed = {arena.id for arena in await VenueRepository(mongo_client).get_arenas()}
        if body.arena_id not in allowed or body.arena_id not in venue_allowed:
            raise HTTPException(status_code=400, detail="Arena is not enabled for this event")
    updated = await repo.update_arena_id(match_id, body.arena_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Match not found")
    return updated


@router.post("/{match_id}/lock", response_model=Match)
async def lock_match(
    match_id: str,
    force: bool = False,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
    x_client_id: str | None = Header(default=None, alias="X-Client-ID", max_length=64),
):
    # Matches are locked per device (client id) so two iPads sharing a coach
    # login still conflict; username is the fallback for clients without an id.
    holder = x_client_id or current_user
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if existing.is_locked and existing.locked_by == holder:
        return existing
    if force:
        logger.info("Force lock takeover on match %s by %s (was %s)", match_id, holder, existing.locked_by)
        return await repo.force_lock_match(match_id, holder)
    result = await repo.lock_match(match_id, holder)
    if not result:
        logger.warning("Lock attempt on already-locked match %s", match_id)
        raise HTTPException(
            status_code=423,
            detail={"message": "Match is already locked", "locked_by": existing.locked_by},
        )
    return result


@router.post("/{match_id}/unlock", response_model=Match)
async def unlock_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
    x_client_id: str | None = Header(default=None, alias="X-Client-ID", max_length=64),
):
    holder = x_client_id or current_user
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    result = await repo.unlock_match(match_id, holder)
    if not result:
        logger.warning("Unlock attempt failed for match %s — not locked by caller", match_id)
        raise HTTPException(status_code=403, detail="Match is locked by another device")
    return result
