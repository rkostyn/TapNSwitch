"""Deleting an event or match together with everything under it.

Events own matches, matches own rounds and throws (throws also carry the
event id). Without this, children linger until the one-year TTL index removes
them. The parent goes first: once an event is gone no new match can be created
for it, so the child sweep cannot miss late arrivals.
"""
from app.db.mongo import MongoClient
from app.logger import get_logger
from app.repositories.event_repository import EventRepository
from app.repositories.match_repository import MatchRepository
from app.repositories.round_repository import RoundRepository
from app.repositories.throw_repository import ThrowRepository

logger = get_logger(__name__)


async def _delete_match_children(mongo_client: MongoClient, match_ids: list[str]) -> None:
    await RoundRepository(mongo_client).delete_rounds_by_match_ids(match_ids)
    await ThrowRepository(mongo_client).delete_throws_by_match_ids(match_ids)


async def delete_match(mongo_client: MongoClient, match_id: str) -> bool:
    """Delete a match, its rounds and its throws. False if the match is unknown."""
    if not await MatchRepository(mongo_client).delete_match(match_id):
        return False
    await _delete_match_children(mongo_client, [match_id])
    logger.info("Cascade-deleted match %s", match_id)
    return True


async def delete_event(mongo_client: MongoClient, event_id: str) -> bool:
    """Delete an event with its matches, their rounds, and all its throws.
    False if the event is unknown."""
    if not await EventRepository(mongo_client).delete_event(event_id):
        return False
    match_repo = MatchRepository(mongo_client)
    match_ids = await match_repo.get_match_ids_by_event(event_id)
    await match_repo.delete_matches_by_event(event_id)
    await _delete_match_children(mongo_client, match_ids)
    await ThrowRepository(mongo_client).delete_throws_by_event(event_id)
    logger.info("Cascade-deleted event %s (%d matches)", event_id, len(match_ids))
    return True
