import json
import os
import re

from app.models.venue import Arena

DEFAULT_VENUE_ID = "default"


def default_arenas_from_env() -> list[Arena]:
    raw = (os.getenv("VENUE_ARENAS") or "").strip()
    if raw:
        try:
            payload = json.loads(raw)
            if isinstance(payload, list) and payload:
                return [Arena(**entry) for entry in payload]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return [
        Arena(id="blue-left", label="Blue - Left"),
        Arena(id="black-right", label="Black - Right"),
    ]


def slugify_arena_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-")
    return slug or "lane"
