from app.models.event import Event
from app.models.lane import ArenaCard, LaneBoard, LaneGroup, LaneInfo
from app.repositories.event_repository import EventRepository
from app.venue import ARENAS, VENUE_NAME, normalize_arena_ids


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
        players=event.players,
        source=event.source,
        checkfront_booking_code=event.checkfront_booking_code,
        start_timestamp=event.start_timestamp,
        checkfront_qty=event.checkfront_qty,
        suggested_arena_count=event.suggested_arena_count,
        suggested_arena_ids=event.suggested_arena_ids,
        arena_ids=event.arena_ids,
    )


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
            arena_id=arena.arena_id,
            name=arena.name,
            color=arena.color,
            text_color=arena.text_color,
            lanes=[LaneInfo(lane_id=lane.lane_id, label=lane.label) for lane in arena.lanes],
            group=as_lane_group(by_arena[arena.arena_id]) if arena.arena_id in by_arena else None,
        )
        for arena in ARENAS
    ]
    return LaneBoard(venue=VENUE_NAME, arenas=arenas, waiting=waiting)


async def assign_event_arenas(
    repo: EventRepository,
    event: Event,
    arena_ids: list[str],
) -> Event:
    wanted = normalize_arena_ids(arena_ids)
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
