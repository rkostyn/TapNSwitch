from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MatchCreate(BaseModel):
    event_id: Optional[str] = Field(default=None, max_length=64)
    player_1_id: str = Field(min_length=1, max_length=64)
    player_2_id: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=1)


class Match(BaseModel):
    match_id: str
    event_id: Optional[str] = None
    player_1_id: str
    player_2_id: str
    sequence: int
    timestamp: datetime
    is_locked: bool = False
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    is_finished: bool = False
    finished_at: Optional[datetime] = None
