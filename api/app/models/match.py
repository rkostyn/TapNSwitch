from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MatchCreate(BaseModel):
    event_id: Optional[str] = Field(default=None, max_length=64)
    player_1_id: str = Field(min_length=1, max_length=64)
    player_2_id: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=1)
    match_type: str = Field(default="swiss", pattern="^(swiss|bracket)$")
    rounds_per_match: int = Field(default=2, ge=1, le=10)


class MatchRoundsUpdate(BaseModel):
    rounds_per_match: int = Field(ge=1, le=10)


class MatchArenaUpdate(BaseModel):
    arena_id: str | None = Field(default=None, max_length=64)


class Match(BaseModel):
    match_id: str
    event_id: Optional[str] = None
    player_1_id: Optional[str] = None
    player_2_id: Optional[str] = None
    sequence: int
    match_type: str = "swiss"
    rounds_per_match: int = 2
    bracket_round: Optional[int] = None
    bracket_slot: Optional[int] = None
    arena_id: Optional[str] = None
    winner_id: Optional[str] = None
    timestamp: datetime
    is_locked: bool = False
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    is_finished: bool = False
    finished_at: Optional[datetime] = None
