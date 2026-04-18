# Models

Pydantic models for request bodies and responses. Invalid input returns `422 Unprocessable Entity` before reaching any route handler.

---

## Auth (`auth.py`)

### `RegisterRequest`
| Field | Type | Constraints |
|---|---|---|
| `username` | `str` | min 3, max 32 |
| `password` | `str` | min 10, max 128 |
| `email` | `str` | max 254 |
| `registration_token` | `str` | max 128 |

### `RegisterResponse`
| Field | Type |
|---|---|
| `user_id` | `str` |
| `username` | `str` |
| `email` | `str` |

### `LoginRequest`
| Field | Type | Notes |
|---|---|---|
| `credentials` | `str` | base64-encoded `username:password` |

### `TokenResponse`
| Field | Type | Default |
|---|---|---|
| `access_token` | `str` | — |
| `token_type` | `str` | `"bearer"` |
| `expires_in` | `int` | `3600` |

---

## User (`user.py`)

### `User`
| Field | Type | Notes |
|---|---|---|
| `user_id` | `str` | — |
| `user_name` | `str` | — |
| `email` | `str \| None` | — |
| `created_at` | `datetime \| None` | — |

---

## Event (`event.py`)

### `EventCreate`
| Field | Type | Constraints |
|---|---|---|
| `venue_id` | `str` | min 1, max 128 |
| `start_timestamp` | `datetime \| None` | optional |

### `Event`
| Field | Type | Default |
|---|---|---|
| `event_id` | `str` | — |
| `venue_id` | `str` | — |
| `start_timestamp` | `datetime \| None` | `None` |
| `timestamp` | `datetime` | server-assigned |
| `is_locked` | `bool` | `False` |
| `locked_by` | `str \| None` | `None` |
| `locked_at` | `datetime \| None` | `None` |
| `is_finished` | `bool` | `False` |
| `finished_at` | `datetime \| None` | `None` |

---

## Match (`match.py`)

### `MatchCreate`
| Field | Type | Constraints |
|---|---|---|
| `event_id` | `str \| None` | max 64, optional |
| `player_1_id` | `str` | min 1, max 64 |
| `player_2_id` | `str` | min 1, max 64 |
| `sequence` | `int` | ≥ 1 |

### `Match`
| Field | Type | Default |
|---|---|---|
| `match_id` | `str` | — |
| `event_id` | `str \| None` | `None` |
| `player_1_id` | `str` | — |
| `player_2_id` | `str` | — |
| `sequence` | `int` | — |
| `timestamp` | `datetime` | server-assigned |
| `is_locked` | `bool` | `False` |
| `locked_by` | `str \| None` | `None` |
| `locked_at` | `datetime \| None` | `None` |
| `is_finished` | `bool` | `False` |
| `finished_at` | `datetime \| None` | `None` |

---

## Round (`round.py`)

### `RoundCreate`
| Field | Type | Constraints |
|---|---|---|
| `match_id` | `str` | min 1, max 64 |
| `player_1_id` | `str` | min 1, max 64 |
| `player_2_id` | `str` | min 1, max 64 |
| `sequence` | `int` | ≥ 1 |

### `Round`
| Field | Type | Default |
|---|---|---|
| `round_id` | `str` | — |
| `match_id` | `str` | — |
| `player_1_id` | `str` | — |
| `player_2_id` | `str` | — |
| `sequence` | `int` | — |
| `timestamp` | `datetime` | server-assigned |
| `is_locked` | `bool` | `False` |
| `locked_by` | `str \| None` | `None` |
| `locked_at` | `datetime \| None` | `None` |

---

## Throw (`throw.py`)

### `ThrowSubmit`
| Field | Type | Constraints | Notes |
|---|---|---|---|
| `throw_id` | `str \| None` | — | **ignored** — server assigns |
| `timestamp` | `datetime \| None` | — | **ignored** — server assigns |
| `player_id` | `str` | min 1, max 64 | — |
| `round_id` | `str` | min 1, max 64 | — |
| `match_id` | `str` | min 1, max 64 | — |
| `event_id` | `str \| None` | max 64, optional | — |
| `venue_id` | `str \| None` | max 128, optional | — |
| `points` | `int` | ≥ 0 | — |
| `clutch_called` | `bool \| None` | — | default `False` |
| `is_premier` | `bool \| None` | — | default `False` |
| `is_drop` | `bool \| None` | — | default `False` |

### `ThrowsGet` (search query)
| Field | Type | Notes |
|---|---|---|
| `player_id` | `str \| None` | filter by player |
| `round_id` | `str \| None` | filter by round |
| `match_id` | `str \| None` | filter by match |
| `event_id` | `str \| None` | filter by event |
| `venue_id` | `str \| None` | filter by venue |

---

## Player (`player.py`)

### `PlayerCreate`
| Field | Type | Constraints |
|---|---|---|
| `player_name` | `str` | min 1, max 128, unique |
| `user_id` | `str \| None` | max 64, optional |

### `Player`
| Field | Type |
|---|---|
| `player_id` | `str` |
| `player_name` | `str` |
| `user_id` | `str \| None` |
| `created_at` | `datetime` |
