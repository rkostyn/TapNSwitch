from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    venue_id: str = Field(min_length=1, max_length=128)
    start_timestamp: Optional[datetime] = None


class Event(BaseModel):
    event_id: str
    venue_id: str
    start_timestamp: Optional[datetime] = None
    timestamp: datetime
    is_locked: bool = False
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    is_finished: bool = False
    finished_at: Optional[datetime] = None
