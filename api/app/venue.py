"""Baltimore Urban Axes floor layout.

Keep this boring on purpose. The building has 6 colored arenas. Each arena
has 2 lanes so two people can throw at the same time during a match.

    Red      Green     Blue
    Yellow   White     Black

Staff put a Checkfront group on one or more colors. A small group usually
needs 1 arena (2 lanes). Bigger groups need more colors, matching how
Baltimore books: 4–6, 7–10, and 11–20 throwers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Lane:
    lane_id: str
    label: str


@dataclass(frozen=True)
class Arena:
    arena_id: str
    name: str
    color: str
    text_color: str
    lanes: tuple[Lane, Lane]


ARENAS: tuple[Arena, ...] = (
    Arena("red", "Red", "#dc2626", "#ffffff", (Lane("red-1", "Lane 1"), Lane("red-2", "Lane 2"))),
    Arena("green", "Green", "#16a34a", "#ffffff", (Lane("green-1", "Lane 1"), Lane("green-2", "Lane 2"))),
    Arena("blue", "Blue", "#2563eb", "#ffffff", (Lane("blue-1", "Lane 1"), Lane("blue-2", "Lane 2"))),
    Arena("yellow", "Yellow", "#eab308", "#111827", (Lane("yellow-1", "Lane 1"), Lane("yellow-2", "Lane 2"))),
    Arena("white", "White", "#e5e7eb", "#111827", (Lane("white-1", "Lane 1"), Lane("white-2", "Lane 2"))),
    Arena("black", "Black", "#171717", "#ffffff", (Lane("black-1", "Lane 1"), Lane("black-2", "Lane 2"))),
)

ARENA_IDS = {arena.arena_id for arena in ARENAS}
ARENA_BY_ID = {arena.arena_id: arena for arena in ARENAS}

VENUE_NAME = "Baltimore Urban Axes"


def suggested_arena_count(player_count: int) -> int:
    """How many colored arenas a group probably needs."""
    size = max(int(player_count or 0), 1)
    if size <= 6:
        return 1
    if size <= 10:
        return 2
    if size <= 20:
        return 3
    return min(6, (size + 5) // 6)


def guess_arena_ids(*texts: str) -> list[str]:
    """If Checkfront's item name mentions a color, hint that arena."""
    blob = " ".join(text or "" for text in texts).casefold()
    found: list[str] = []
    for arena in ARENAS:
        if arena.arena_id in blob and arena.arena_id not in found:
            found.append(arena.arena_id)
    return found


def lanes_for_arena_ids(arena_ids: list[str]) -> list[str]:
    """Expand occupied colors into the 2 physical lanes in each arena."""
    lanes: list[str] = []
    for raw in arena_ids or []:
        arena = ARENA_BY_ID.get((raw or "").strip().casefold())
        if not arena:
            continue
        lanes.extend(lane.lane_id for lane in arena.lanes)
    return lanes


def lane_label(lane_id: str | None) -> str:
    if not lane_id:
        return ""
    arena_id = lane_id.rsplit("-", 1)[0]
    arena = ARENA_BY_ID.get(arena_id)
    if not arena:
        return lane_id
    lane = next((item for item in arena.lanes if item.lane_id == lane_id), None)
    return f"{arena.name} · {lane.label}" if lane else lane_id


def normalize_arena_ids(arena_ids: list[str]) -> list[str]:
    seen: list[str] = []
    unknown: list[str] = []
    for raw in arena_ids:
        arena_id = (raw or "").strip().casefold()
        if not arena_id:
            continue
        if arena_id not in ARENA_IDS:
            unknown.append(raw)
            continue
        if arena_id not in seen:
            seen.append(arena_id)
    if unknown:
        raise ValueError(f"Unknown arena: {', '.join(unknown)}")
    return seen
