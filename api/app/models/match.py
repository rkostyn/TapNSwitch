from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MatchCreate(BaseModel):
    event_id: Optional[str] = None
    player_1_id: str
    player_2_id: str
    sequence: int


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
