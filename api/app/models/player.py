from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Player(BaseModel):
    player_id: str
    player_name: str
    user_id: Optional[str] = None
    created_at: datetime


class PlayerCreate(BaseModel):
    player_name: str = Field(min_length=1, max_length=128)
    user_id: Optional[str] = Field(default=None, max_length=64)
