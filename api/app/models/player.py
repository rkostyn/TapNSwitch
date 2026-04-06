from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Player(BaseModel):
    player_id: str
    player_name: str
    user_id: Optional[str] = None
    created_at: datetime


class PlayerCreate(BaseModel):
    player_name: str
    user_id: Optional[str] = None
