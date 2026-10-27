from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ThrowSubmit(BaseModel):
    throw_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    player_id: str = Field(min_length=1, max_length=64)
    round_id: str = Field(min_length=1, max_length=64)
    match_id: str = Field(min_length=1, max_length=64)
    event_id: Optional[str] = Field(default=None, max_length=64)
    venue_id: Optional[str] = Field(default=None, max_length=128)
    points: int = Field(ge=0)
    clutch_called: Optional[bool] = False
    is_premier: Optional[bool] = False
    is_drop: Optional[bool] = False


# Get a single throw
class ThrowGet(BaseModel):
    throw_id: str

# Get all throws matching criteria (e.g. all throws for a player, round, match, event, or venue)
class ThrowsGet(BaseModel):
    player_id: Optional[str] = None
    round_id: Optional[str] = None
    match_id: Optional[str] = None
    event_id: Optional[str] = None
    venue_id: Optional[str] = None

class Throw(BaseModel):
    throw_id: str
    timestamp: datetime
    player_id: str
    round_id: str
    match_id: str
    event_id: Optional[str] = None
    venue_id: Optional[str] = None
    points:  int
    clutch_called: Optional[bool] = False
    is_premier: Optional[bool] = False
    is_drop: Optional[bool] = False
