from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ArenaAssign(BaseModel):
    arena_ids: list[str] = Field(max_length=6)


class LaneInfo(BaseModel):
    lane_id: str
    label: str


class LaneGroup(BaseModel):
    event_id: str
    event_name: Optional[str] = None
    event_type: Literal["standard", "tournament"] = "standard"
    players: list[str] = []
    source: str = "manual"
    checkfront_booking_code: Optional[str] = None
    start_timestamp: Optional[datetime] = None
    checkfront_qty: int = 1
    suggested_arena_count: int = 1
    suggested_arena_ids: list[str] = []
    arena_ids: list[str] = []


class VenueArena(BaseModel):
    """One colored arena and its lanes, as laid out in ``app/venue.py``."""
    arena_id: str
    name: str
    color: str
    text_color: str
    lanes: list[LaneInfo]


class Venue(BaseModel):
    """The static floor layout served by ``GET /venue``."""
    venue: str
    arenas: list[VenueArena]


class ArenaCard(VenueArena):
    """An arena on the live lane board, with the group occupying it."""
    group: Optional[LaneGroup] = None


class LaneBoard(BaseModel):
    venue: str
    arenas: list[ArenaCard]
    waiting: list[LaneGroup]
