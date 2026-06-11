"""Pure tournament logic: swiss pairing, standings and single-elimination brackets."""
import uuid
from datetime import UTC, datetime

from app.logger import get_logger

logger = get_logger(__name__)


def _round_robin_rounds(players: list[str]) -> list[list[tuple[str, str]]]:
    """Circle-method round robin. Returns a list of rounds, each a list of pairs."""
    ps = list(players)
    if len(ps) % 2:
        ps.append(None)
    n = len(ps)
    rounds = []
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ps[i], ps[n - 1 - i]
            if a is not None and b is not None:
                pairs.append((a, b))
        rounds.append(pairs)
        ps = [ps[0], ps[-1]] + ps[1:-1]
    return rounds


def build_swiss_pairings(
    players: list[str],
    late_players: list[str],
    matches_per_player: int,
) -> list[tuple[str, str]]:
    """Build an ordered swiss schedule where each player gets matches_per_player
    matches. Pairs involving late players are pushed to the end of the schedule
    so their games start later. Rematches occur only when the pool is too small
    to avoid them.
    """
    if len(players) < 2:
        return []
    needed = {p: matches_per_player for p in players}
    pairings: list[tuple[str, str]] = []
    # Cycle the round robin until everyone has enough matches; one extra cycle
    # bounds the loop when the player count makes an exact fill impossible.
    for _ in range(matches_per_player + 1):
        for round_pairs in _round_robin_rounds(players):
            for a, b in round_pairs:
                if needed[a] > 0 and needed[b] > 0:
                    pairings.append((a, b))
                    needed[a] -= 1
                    needed[b] -= 1
        if all(v <= 0 for v in needed.values()):
            break
    late = set(late_players)
    pairings.sort(key=lambda pair: pair[0] in late or pair[1] in late)
    return pairings


def compute_swiss_standings(players: list[str], swiss_match_ids: set[str], throws) -> list[dict]:
    """Aggregate throws into per-player standings, sorted by total points with
    rounds-won then highest-single-round as tiebreakers (player name last, for
    determinism)."""
    stats = {
        p: {"player": p, "points": 0, "rounds_won": 0, "highest_round": 0, "matches_played": 0}
        for p in players
    }
    totals_by_round: dict[tuple[str, str], dict[str, int]] = {}
    for t in throws:
        if t.match_id not in swiss_match_ids:
            continue
        round_totals = totals_by_round.setdefault((t.match_id, t.round_id), {})
        round_totals[t.player_id] = round_totals.get(t.player_id, 0) + t.points

    matches_played: dict[str, set[str]] = {}
    for (match_id, _round_id), totals in totals_by_round.items():
        for player, total in totals.items():
            if player not in stats:
                continue
            stats[player]["points"] += total
            stats[player]["highest_round"] = max(stats[player]["highest_round"], total)
            matches_played.setdefault(player, set()).add(match_id)
        ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        if len(ranked) >= 2 and ranked[0][1] > ranked[1][1] and ranked[0][0] in stats:
            stats[ranked[0][0]]["rounds_won"] += 1

    for player, match_ids in matches_played.items():
        if player in stats:
            stats[player]["matches_played"] = len(match_ids)

    return sorted(
        stats.values(),
        key=lambda s: (-s["points"], -s["rounds_won"], -s["highest_round"], s["player"]),
    )


def _seed_order(size: int) -> list[int]:
    """Standard bracket seed placement, e.g. size 8 -> [1,8,4,5,2,7,3,6]."""
    order = [1]
    while len(order) < size:
        n = len(order) * 2
        order = [s for seed in order for s in (seed, n + 1 - seed)]
    return order


def place_winner(doc: dict, slot: int, winner: str) -> None:
    """Put the winner of a match at (round, slot) into its side of the next-round doc."""
    if slot % 2 == 0:
        doc["player_1_id"] = winner
    else:
        doc["player_2_id"] = winner


def build_bracket_matches(
    seeds: list[str],
    event_id: str,
    rounds_per_match: int,
    start_sequence: int = 1,
) -> list[dict]:
    """Build single-elimination match docs for all bracket rounds, seeded so the
    best seed meets the worst. Bye matches in round 1 are pre-finished and their
    winners advanced into round 2.
    """
    n = len(seeds)
    if n < 2:
        raise ValueError("Bracket needs at least 2 players")
    size = 1
    while size < n:
        size *= 2
    total_rounds = size.bit_length() - 1
    slots = [seeds[s - 1] if s <= n else None for s in _seed_order(size)]

    now = datetime.now(UTC)
    matches: list[dict] = []
    index: dict[tuple[int, int], dict] = {}
    seq = start_sequence
    per_round = size // 2
    for rnd in range(1, total_rounds + 1):
        for slot in range(per_round):
            doc = {
                "match_id": str(uuid.uuid4()),
                "event_id": event_id,
                "player_1_id": None,
                "player_2_id": None,
                "sequence": seq,
                "match_type": "bracket",
                "rounds_per_match": rounds_per_match,
                "bracket_round": rnd,
                "bracket_slot": slot,
                "winner_id": None,
                "timestamp": now,
                "is_locked": False,
                "locked_by": None,
                "locked_at": None,
                "is_finished": False,
                "finished_at": None,
            }
            matches.append(doc)
            index[(rnd, slot)] = doc
            seq += 1
        per_round //= 2

    for slot in range(size // 2):
        doc = index[(1, slot)]
        doc["player_1_id"] = slots[2 * slot]
        doc["player_2_id"] = slots[2 * slot + 1]
        winner = doc["player_1_id"] or doc["player_2_id"]
        if doc["player_1_id"] and doc["player_2_id"]:
            continue
        # Bye: only one (or zero) real players in this pairing
        doc["winner_id"] = winner
        doc["is_finished"] = True
        doc["finished_at"] = now
        if winner and total_rounds > 1:
            place_winner(index[(2, slot // 2)], slot, winner)

    logger.info("Built bracket for event %s: %d players, %d matches", event_id, n, len(matches))
    return matches


def compute_match_winner(player_1_id: str | None, player_2_id: str | None, throws) -> str | None:
    """Winner of a match from its throws: most rounds won, then total points,
    then highest single round. Returns None when fully tied or undecidable."""
    players = [p for p in (player_1_id, player_2_id) if p]
    if len(players) == 1:
        return players[0]
    if not players:
        return None

    totals_by_round: dict[str, dict[str, int]] = {}
    for t in throws:
        round_totals = totals_by_round.setdefault(t.round_id, {})
        round_totals[t.player_id] = round_totals.get(t.player_id, 0) + t.points

    rounds_won = {p: 0 for p in players}
    points = {p: 0 for p in players}
    highest = {p: 0 for p in players}
    for totals in totals_by_round.values():
        for p in players:
            v = totals.get(p, 0)
            points[p] += v
            highest[p] = max(highest[p], v)
        v1, v2 = totals.get(players[0], 0), totals.get(players[1], 0)
        if v1 > v2:
            rounds_won[players[0]] += 1
        elif v2 > v1:
            rounds_won[players[1]] += 1

    def score(p):
        return (rounds_won[p], points[p], highest[p])

    p1, p2 = players
    if score(p1) > score(p2):
        return p1
    if score(p2) > score(p1):
        return p2
    return None
