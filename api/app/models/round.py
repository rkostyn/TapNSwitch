from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RoundCreate(BaseModel):
    match_id: str
    player_1_id: str
    player_2_id: str
    sequence: int


class Round(BaseModel):
    round_id: str
    match_id: str
    player_1_id: str
    player_2_id: str
    sequence: int
    timestamp: datetime
    is_locked: bool = False
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
