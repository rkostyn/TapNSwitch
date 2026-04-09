from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RoundCreate(BaseModel):
    match_id: str = Field(min_length=1, max_length=64)
    player_1_id: str = Field(min_length=1, max_length=64)
    player_2_id: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=1)


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
