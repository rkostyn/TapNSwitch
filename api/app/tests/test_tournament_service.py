from types import SimpleNamespace

from app.services.tournament import (
    build_bracket_matches,
    build_swiss_pairings,
    compute_match_winner,
    compute_swiss_standings,
)


def throw(player, round_id, points, match_id="m1"):
    return SimpleNamespace(player_id=player, round_id=round_id, points=points, match_id=match_id)


# ---------------------------------------------------------------------------
# Swiss pairings
# ---------------------------------------------------------------------------

def test_swiss_default_two_matches_per_player():
    players = ["A", "B", "C", "D"]
    pairings = build_swiss_pairings(players, [], 2)
    counts = {p: 0 for p in players}
    for a, b in pairings:
        counts[a] += 1
        counts[b] += 1
    assert all(c == 2 for c in counts.values())


def test_swiss_two_players_rematch():
    pairings = build_swiss_pairings(["A", "B"], [], 2)
    assert len(pairings) == 2
    assert {frozenset(p) for p in pairings} == {frozenset(("A", "B"))}


def test_swiss_no_self_pairing():
    pairings = build_swiss_pairings(["A", "B", "C", "D", "E"], [], 3)
    assert all(a != b for a, b in pairings)


def test_swiss_late_players_scheduled_last():
    pairings = build_swiss_pairings(["A", "B", "C", "D"], ["D"], 2)
    involves_late = [("D" in pair) for pair in pairings]
    # Once a late pairing appears, every following pairing also involves the late player
    first_late = involves_late.index(True)
    assert all(involves_late[first_late:])


def test_swiss_single_player_no_matches():
    assert build_swiss_pairings(["A"], [], 2) == []


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def test_standings_sorted_by_points():
    throws = [
        throw("A", "r1", 5), throw("B", "r1", 3),
        throw("A", "r2", 1), throw("B", "r2", 7),
    ]
    standings = compute_swiss_standings(["A", "B"], {"m1"}, throws)
    assert standings[0]["player"] == "B"
    assert standings[0]["points"] == 10
    assert standings[1]["points"] == 6


def test_standings_tiebreak_rounds_won():
    # A and B tie on points but A wins more rounds
    throws = [
        throw("A", "r1", 5), throw("B", "r1", 3),
        throw("A", "r2", 5), throw("B", "r2", 3),
        throw("A", "r3", 0), throw("B", "r3", 4),
    ]
    # totals: A=10, B=10; rounds won: A=2, B=1
    standings = compute_swiss_standings(["A", "B"], {"m1"}, throws)
    assert standings[0]["player"] == "A"
    assert standings[0]["rounds_won"] == 2


def test_standings_tiebreak_highest_round():
    # Equal points and rounds won; B has the higher single round
    throws = [
        throw("A", "r1", 4), throw("B", "r1", 6, match_id="m2"),
        throw("A", "r2", 4), throw("B", "r2", 2, match_id="m2"),
    ]
    standings = compute_swiss_standings(["A", "B"], {"m1", "m2"}, throws)
    assert standings[0]["player"] == "B"
    assert standings[0]["highest_round"] == 6


def test_standings_ignores_non_swiss_matches():
    throws = [
        throw("A", "r1", 5),
        throw("A", "r9", 50, match_id="bracket-match"),
    ]
    standings = compute_swiss_standings(["A"], {"m1"}, throws)
    assert standings[0]["points"] == 5


# ---------------------------------------------------------------------------
# Bracket
# ---------------------------------------------------------------------------

def test_bracket_four_players():
    matches = build_bracket_matches(["S1", "S2", "S3", "S4"], "ev1", 3)
    assert len(matches) == 3
    round1 = [m for m in matches if m["bracket_round"] == 1]
    final = [m for m in matches if m["bracket_round"] == 2]
    assert len(round1) == 2 and len(final) == 1
    # Best seed plays worst seed
    pairs = {frozenset((m["player_1_id"], m["player_2_id"])) for m in round1}
    assert pairs == {frozenset(("S1", "S4")), frozenset(("S2", "S3"))}
    assert all(m["rounds_per_match"] == 3 for m in matches)


def test_bracket_byes_advance_top_seeds():
    matches = build_bracket_matches(["S1", "S2", "S3"], "ev1", 3)
    round1 = {m["bracket_slot"]: m for m in matches if m["bracket_round"] == 1}
    final = [m for m in matches if m["bracket_round"] == 2][0]
    # S1 had a bye and sits in the final already
    bye = [m for m in round1.values() if m["is_finished"]]
    assert len(bye) == 1
    assert bye[0]["winner_id"] == "S1"
    assert "S1" in (final["player_1_id"], final["player_2_id"])


def test_bracket_two_players_single_final():
    matches = build_bracket_matches(["S1", "S2"], "ev1", 1)
    assert len(matches) == 1
    assert matches[0]["rounds_per_match"] == 1


# ---------------------------------------------------------------------------
# Match winner
# ---------------------------------------------------------------------------

def test_match_winner_most_rounds():
    throws = [
        throw("A", "r1", 5), throw("B", "r1", 3),
        throw("A", "r2", 2), throw("B", "r2", 1),
        throw("A", "r3", 0), throw("B", "r3", 5),
    ]
    assert compute_match_winner("A", "B", throws) == "A"


def test_match_winner_tie_returns_none():
    throws = [throw("A", "r1", 3), throw("B", "r1", 3)]
    assert compute_match_winner("A", "B", throws) is None


def test_match_winner_points_tiebreak():
    # 1 round each, but B scored more total points
    throws = [
        throw("A", "r1", 5), throw("B", "r1", 0),
        throw("A", "r2", 0), throw("B", "r2", 7),
    ]
    assert compute_match_winner("A", "B", throws) == "B"


def test_match_winner_single_player_bye():
    assert compute_match_winner("A", None, []) == "A"
