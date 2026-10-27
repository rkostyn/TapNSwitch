"""Recompute match winners from throws and keep bracket progression in sync."""
from app.db.mongo import MongoClient
from app.models.match import Match
from app.models.throw import ThrowsGet
from app.repositories.match_repository import MatchRepository
from app.repositories.throw_repository import ThrowRepository
from app.services.tournament import compute_match_winner
from app.logger import get_logger

logger = get_logger(__name__)


async def update_match_winner(mongo_client: MongoClient, match: Match) -> str | None:
    """Recompute the winner of a match from its throws, persist it, and advance
    the winner into the next bracket round unless that match already finished."""
    throw_repo = ThrowRepository(mongo_client)
    throws = await throw_repo.get_throws_by_criteria(ThrowsGet(match_id=match.match_id))
    winner = compute_match_winner(match.player_1_id, match.player_2_id, throws)
    match_repo = MatchRepository(mongo_client)
    await match_repo.set_winner(match.match_id, winner)

    if (
        match.match_type == "bracket"
        and match.event_id
        and match.bracket_round is not None
        and winner is not None
    ):
        next_match = await match_repo.get_bracket_match(
            match.event_id, match.bracket_round + 1, match.bracket_slot // 2
        )
        if next_match and not next_match.is_finished:
            await match_repo.set_bracket_player(next_match.match_id, match.bracket_slot % 2, winner)
            logger.info("Advanced %s to bracket round %d", winner, match.bracket_round + 1)
    return winner
