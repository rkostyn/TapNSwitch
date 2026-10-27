from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CheckfrontBooking:
    booking_id: str
    code: str
    status: str
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    start_date: datetime | None = None
    item_ids: list[str] = field(default_factory=list)
    item_skus: list[str] = field(default_factory=list)
    qty: int = 1
    extra_player_names: list[str] = field(default_factory=list)

    @property
    def session_key(self) -> str | None:
        if not self.start_date or not self.item_ids:
            return None
        return f"{self.item_ids[0]}:{int(self.start_date.timestamp())}"

    @property
    def player_names(self) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for name in [self.customer_name, *self.extra_player_names]:
            cleaned = name.strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(cleaned)
        return names

    @property
    def event_name(self) -> str:
        if self.item_skus:
            label = self.item_skus[0].replace("-", " ").replace("_", " ").title()
            return f"{label} ({self.code})"
        return f"Checkfront {self.code}"
