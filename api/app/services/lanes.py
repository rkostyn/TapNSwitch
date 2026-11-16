import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.db.redis import RedisClient
from app.models.event import Event
from app.models.lane import ArenaCard, LaneBoard, LaneGroup, LaneInfo, Venue, VenueArena
from app.repositories.event_repository import EventRepository
from app.services.errors import ConflictError
from app.venue import ARENAS, VENUE_NAME, normalize_arena_ids

# Assignments are check-then-write across several event documents, which a
# single Mongo update cannot make atomic (and the standalone deployment has no
# multi-document transactions). Every assignment therefore runs under one
# short Redis lock. Nothing else claims arenas: finishing an event only frees
# them, and the admin PATCH allowlist excludes arena_ids.
ARENA_LOCK_KEY = "lock:arena_assignment"
ARENA_LOCK_TTL_SECONDS = 10
ARENA_LOCK_WAIT_SECONDS = 3.0


class ArenaOccupiedError(Exception):
    def __init__(self, arena_id: str, event: Event):
        self.arena_id = arena_id
        self.event = event
        label = event.event_name or "another group"
        super().__init__(f"{arena_id.title()} is already used by {label}")


def as_lane_group(event: Event) -> LaneGroup:
    return LaneGroup(
        event_id=event.event_id,
        event_name=event.event_name,
        event_type=event.event_type,
        players=event.players,
        source=event.source,
        checkfront_booking_code=event.checkfront_booking_code,
        start_timestamp=event.start_timestamp,
        checkfront_qty=event.checkfront_qty,
        suggested_arena_count=event.suggested_arena_count,
        suggested_arena_ids=event.suggested_arena_ids,
        arena_ids=event.arena_ids,
    )


def venue_arenas() -> list[VenueArena]:
    return [
        VenueArena(
            arena_id=arena.arena_id,
            name=arena.name,
            color=arena.color,
            text_color=arena.text_color,
            lanes=[LaneInfo(lane_id=lane.lane_id, label=lane.label) for lane in arena.lanes],
        )
        for arena in ARENAS
    ]


def venue_layout() -> Venue:
    return Venue(venue=VENUE_NAME, arenas=venue_arenas())


async def build_lane_board(repo: EventRepository) -> LaneBoard:
    open_events = await repo.get_open_events()
    by_arena: dict[str, Event] = {}
    waiting: list[LaneGroup] = []
    for event in open_events:
        if event.arena_ids:
            for arena_id in event.arena_ids:
                by_arena.setdefault(arena_id, event)
        else:
            waiting.append(as_lane_group(event))

    arenas = [
        ArenaCard(
            **arena.model_dump(),
            group=as_lane_group(by_arena[arena.arena_id]) if arena.arena_id in by_arena else None,
        )
        for arena in venue_arenas()
    ]
    return LaneBoard(venue=VENUE_NAME, arenas=arenas, waiting=waiting)


@asynccontextmanager
async def arena_assignment_lock(redis_client: RedisClient) -> AsyncIterator[None]:
    deadline = time.monotonic() + ARENA_LOCK_WAIT_SECONDS
    while (token := await redis_client.acquire_lock(ARENA_LOCK_KEY, ARENA_LOCK_TTL_SECONDS)) is None:
        if time.monotonic() >= deadline:
            raise ConflictError("Another arena assignment is in progress; try again")
        await asyncio.sleep(0.05)
    try:
        yield
    finally:
        await redis_client.release_lock(ARENA_LOCK_KEY, token)


async def assign_event_arenas(
    repo: EventRepository,
    redis_client: RedisClient,
    event: Event,
    arena_ids: list[str],
) -> Event:
    wanted = normalize_arena_ids(arena_ids)
    async with arena_assignment_lock(redis_client):
        return await _assign_unlocked(repo, event, wanted)


async def _assign_unlocked(repo: EventRepository, event: Event, wanted: list[str]) -> Event:
    open_events = await repo.get_open_events()
    for other in open_events:
        if other.event_id == event.event_id:
            continue
        taken = set(other.arena_ids)
        clash = next((arena_id for arena_id in wanted if arena_id in taken), None)
        if clash:
            raise ArenaOccupiedError(clash, other)
    updated = await repo.update_event_fields(event.event_id, {"arena_ids": wanted})
    if not updated:
        raise ValueError("Event not found")
    return updated
