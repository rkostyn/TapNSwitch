"""Shared checks before a match is changed."""
from app.db.mongo import MongoClient
from app.models.match import Match
from app.repositories.event_repository import EventRepository
from app.repositories.match_repository import MatchRepository
from app.services.errors import LockedError, NotFoundError


async def get_match_or_404(repo: MatchRepository, match_id: str) -> Match:
    match = await repo.get_match(match_id)
    if not match:
        raise NotFoundError("Match not found")
    return match


async def load_scorable_match(
    mongo_client: MongoClient,
    match_id: str,
    holder: str,
    *,
    allow_finished: bool,
) -> Match:
    """Load a match that ``holder`` (a device id or username) may score.

    Checks, in order: the match exists (404); unless ``allow_finished``, it is
    not finished (423); it is not locked by someone else (423); its event, if
    any, is not finished (423).
    """
    match = await get_match_or_404(MatchRepository(mongo_client), match_id)
    if not allow_finished and match.is_finished:
        raise LockedError("Match is finished")
    if match.is_locked and match.locked_by != holder:
        raise LockedError("Match is locked by another device")
    if match.event_id:
        event = await EventRepository(mongo_client).get_event(match.event_id)
        if event and event.is_finished:
            raise LockedError("Event is finished")
    return match
