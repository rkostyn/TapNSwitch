from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

EventType = Literal["standard", "tournament"]
PairingStyle = Literal["round_robin", "swiss"]


def default_pairing_style(event_type: Optional[str]) -> PairingStyle:
    """Tournament events default to swiss; standard (everyday) events to round robin."""
    return "swiss" if event_type == "tournament" else "round_robin"


class EventCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=128)
    players: list[str] = Field(min_length=1)
    start_timestamp: Optional[datetime] = None
    swiss_matches_per_player: int = Field(default=2, ge=1, le=20)
    swiss_rounds_per_match: int = Field(default=2, ge=1, le=10)
    event_type: EventType = "standard"


class EventTypeUpdate(BaseModel):
    event_type: EventType


class PlayerAdd(BaseModel):
    player_name: str = Field(min_length=1, max_length=128)


class LateUpdate(BaseModel):
    late: bool


class SwissConfigUpdate(BaseModel):
    swiss_matches_per_player: int = Field(ge=1, le=20)
    swiss_rounds_per_match: int = Field(ge=1, le=10)
    pairing_style: Optional[PairingStyle] = None


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
    event_type: EventType = "standard"
    event_name: Optional[str] = None
    players: list[str] = []
    late_players: list[str] = []
    created_by: Optional[str] = None
    source: Literal["manual", "checkfront"] = "manual"
    checkfront_booking_id: Optional[str] = None
    checkfront_booking_code: Optional[str] = None
    checkfront_session_key: Optional[str] = None
    checkfront_booking_ids: list[str] = []
    checkfront_item_skus: list[str] = []
    checkfront_qty: int = 1
    suggested_arena_count: int = 1
    suggested_arena_ids: list[str] = []
    arena_ids: list[str] = []
    start_timestamp: Optional[datetime] = None
    timestamp: datetime
    pairing_style: PairingStyle = "round_robin"
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

    @model_validator(mode="before")
    @classmethod
    def _defaults_by_type(cls, data):
        """Events stored before event types existed read back as standard, and
        an event stored without a pairing style gets its own type's default."""
        if isinstance(data, dict):
            data = dict(data)
            if data.get("event_type") is None:
                data["event_type"] = "standard"
            if data.get("pairing_style") is None:
                data["pairing_style"] = default_pairing_style(data["event_type"])
        return data
