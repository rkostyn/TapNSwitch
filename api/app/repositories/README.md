# Repositories

Async data-access layer sitting between routes and MongoDB. Each repository owns one collection.

| File | Collection | Notes |
|---|---|---|
| `user_repository.py` | `users` | Enforces unique `user_name` and `email` with an application-level pre-check before insert. |
| `player_repository.py` | `players` | Enforces unique `player_name` with an application-level pre-check before insert. |
| `event_repository.py` | `events` | — |
| `match_repository.py` | `matches` | — |
| `round_repository.py` | `rounds` | — |
| `throw_repository.py` | `throws` | Assigns `throw_id` (UUID) and `timestamp` server-side, ignoring any client-supplied values. |

## Duplicate handling

Real MongoDB enforces uniqueness via the indexes in `db/indexes.json`. The in-memory test fake (`tests/fakes.py`) does not enforce indexes, so repositories that need uniqueness add an application-level `find_one` pre-check. `DuplicateKeyError` from pymongo is still caught as a race-condition fallback for production.
