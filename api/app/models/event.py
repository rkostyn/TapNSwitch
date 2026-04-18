from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EventCreate(BaseModel):
    venue_id: Optional[str] = None
    start_timestamp: Optional[datetime] = None


class Event(BaseModel):
    event_id: str
    venue_id: Optional[str] = None
    start_timestamp: Optional[datetime] = None
    timestamp: datetime
    is_locked: bool = False
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    is_finished: bool = False
    finished_at: Optional[datetime] = None
