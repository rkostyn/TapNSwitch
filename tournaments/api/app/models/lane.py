from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ArenaAssign(BaseModel):
    arena_ids: list[str] = Field(max_length=6)


class LaneInfo(BaseModel):
    lane_id: str
    label: str


class LaneGroup(BaseModel):
    event_id: str
    event_name: Optional[str] = None
    players: list[str] = []
    source: str = "manual"
    checkfront_booking_code: Optional[str] = None
    start_timestamp: Optional[datetime] = None
    checkfront_qty: int = 1
    suggested_arena_count: int = 1
    suggested_arena_ids: list[str] = []
    arena_ids: list[str] = []


class ArenaCard(BaseModel):
    arena_id: str
    name: str
    color: str
    text_color: str
    lanes: list[LaneInfo]
    group: Optional[LaneGroup] = None


class LaneBoard(BaseModel):
    venue: str
    arenas: list[ArenaCard]
    waiting: list[LaneGroup]
