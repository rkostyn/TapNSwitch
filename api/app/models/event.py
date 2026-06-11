from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=128)
    players: list[str] = Field(min_length=1)
    start_timestamp: Optional[datetime] = None
    swiss_matches_per_player: int = Field(default=2, ge=1, le=20)
    swiss_rounds_per_match: int = Field(default=2, ge=1, le=10)


class PlayerAdd(BaseModel):
    player_name: str = Field(min_length=1, max_length=128)


class LateUpdate(BaseModel):
    late: bool


class SwissConfigUpdate(BaseModel):
    swiss_matches_per_player: int = Field(ge=1, le=20)
    swiss_rounds_per_match: int = Field(ge=1, le=10)


class SwissStanding(BaseModel):
    player: str
    points: int = 0
    rounds_won: int = 0
    highest_round: int = 0
    matches_played: int = 0


class BracketGenerate(BaseModel):
    rounds_per_match: int = Field(default=3, ge=1, le=10)


class Event(BaseModel):
    event_id: str
    event_name: Optional[str] = None
    players: list[str] = []
    late_players: list[str] = []
    created_by: Optional[str] = None
    start_timestamp: Optional[datetime] = None
    timestamp: datetime
    swiss_matches_per_player: int = 2
    swiss_rounds_per_match: int = 2
    swiss_generated_at: Optional[datetime] = None
    swiss_standings: Optional[list[SwissStanding]] = None
    standings_generated_at: Optional[datetime] = None
    bracket_rounds_per_match: int = 3
    bracket_generated_at: Optional[datetime] = None
    is_locked: bool = False
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    is_finished: bool = False
    finished_at: Optional[datetime] = None
