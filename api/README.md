# Axes API

REST API for scoring and managing axe throwing matches. Built with FastAPI, MongoDB, and Redis.

## Features

- Token-based authentication with rate limiting
- Invite-only user registration via registration tokens
- Hierarchical data model: Events → Matches → Rounds → Throws
- Optimistic locking on events and matches to prevent concurrent write conflicts
- Prometheus metrics at `/metrics`
- Web-based admin panel at `/admin`

## Stack

- **Framework:** FastAPI (async)
- **Database:** MongoDB (via the PyMongo async driver)
- **Cache / Sessions:** Redis
- **Auth:** Bearer tokens (stored as SHA-256 hashes in Redis, TTL 1 hour)

## Environment Variables

All variables are read through one `Settings` class in `app/settings.py` (pydantic-settings). Values are stripped, and an empty value counts as unset. `get_settings()` always reflects the current environment (it is rebuilt whenever `os.environ` changes), so tests can use `monkeypatch.setenv`.

### Required

| Variable | Description |
|---|---|
| `MONGODB_URI` | Full MongoDB connection URI, e.g. `mongodb://user:pass@host:27017/admin?replicaSet=rs0&tls=true` |
| `REDIS_URI` | Full Redis connection URI, e.g. `redis://localhost:6379/0` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `ENV` | — | Set to `production` to disable API docs and send HSTS |
| `APP_NAME` | — | Application name shown in OpenAPI UI |
| `LOG_LEVEL` | `INFO` | Python log level |
| `CORS_ORIGINS` | — (all origins) | Comma-separated allowed origins |
| `INITIAL_ADMIN_PASSWORD` | — | If set and no admin exists, create one on startup |
| `INITIAL_ADMIN_USERNAME` | `admin` | Username for that first admin |
| `INITIAL_ADMIN_EMAIL` | `admin@local.dev` | Email for that first admin |
| `CHECKFRONT_WEBHOOK_SECRET` | — | Shared secret for `POST /integrations/checkfront/webhook`; the webhook answers 503 until set |
| `CHECKFRONT_API_URL` | — | Checkfront API base URL, e.g. `https://<site>.checkfront.com/api/3.0` |
| `CHECKFRONT_API_KEY` / `CHECKFRONT_API_SECRET` | — | Checkfront API token; pull sync needs URL, key and secret |
| `CHECKFRONT_API_CLIENT_IP` | `127.0.0.1` | Sent to Checkfront as `X-Forwarded-For` |
| `CHECKFRONT_SYNC_INTERVAL_SECONDS` | `0` | Background pull interval; `0` disables it. Must be an integer |
| `CHECKFRONT_GROUP_MODE` | `session` | `booking` (one event per booking) or `session` (merge by time slot + item); anything else means `session` |
| `CHECKFRONT_PLAYER_FIELD_KEYS` | — | Comma-separated custom field keys holding extra thrower names |
| `CHECKFRONT_ACCEPT_STATUSES` | `PAID,CONF,PEND,HOLD,WAIT` | Comma-separated booking statuses to import |
| `CHECKFRONT_PULL_FETCH_DETAIL` | `true` | Fetch each booking's detail during pull; `0`/`false`/`no` turn it off |
| `VENUE_TIMEZONE` | `America/New_York` | Timezone for "today" filters (`CHECKFRONT_TIMEZONE` is the legacy fallback) |

`FORWARDED_ALLOW_IPS` is read by uvicorn, not the app: it lists the proxy IPs whose `X-Forwarded-For` is trusted (default `127.0.0.1`). The app itself does not read `CF-Connecting-IP`.

## Event types

Everyday groups and tournaments run side by side in one deployment. Each event has an `event_type`, `standard` (the default) or `tournament`, chosen with `event_type` on `POST /event`. Checkfront imports are always `standard`, and events stored before the field existed read back as `standard`.

| Behaviour | `standard` | `tournament` |
|-----------|------------|--------------|
| Default `pairing_style` (on creation, and for a stored event without one) | `round_robin` | `swiss` |
| Lane (`arena_id`) on generated swiss/round-robin matches, including late entries | not set (`null`) | dealt round the event's lanes (`red-1`, `red-2`, ...) from its assigned arenas |

`PUT /event/{event_id}/type` with `{"event_type": "standard" | "tournament"}` changes the type and resets `pairing_style` to the new type's default; setting the current type changes nothing. It answers 404 for an unknown event, 423 once the event is finished, and 409 once the event has any match, or its group stage or bracket has been generated. The style can still be changed afterwards with `PUT /event/{event_id}/swiss-config`. The admin PATCH cannot change `event_type`, so that rule cannot be bypassed.

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # runtime deps + pytest + ruff

# Start dependencies
docker run -d -p 27017:27017 mongo
docker run -d -p 6379:6379 redis

# Set required environment variables
export MONGODB_URI="mongodb://localhost:27017/admin"
export REDIS_URI="redis://localhost:6379/0"

# Run the API
uvicorn app.main:app --reload --port 8000
```

API docs (Swagger UI) will be available at `http://localhost:8000/`.

## Data Model

```
Event
└── Match (player_1 vs player_2, sequence number)
    └── Round
        └── Throw (player, points, clutch_called, is_premier, is_drop)
```

**Locking:** Events and matches can be locked by a user to prevent concurrent edits. A locked resource can only be modified by the user who locked it, or by an admin.

**Finishing:** Once an event or match is marked finished, no new child records can be created under it.

**Deleting:** `DELETE /event/{id}` also deletes the event's matches, their rounds, and its throws; `DELETE /match/{id}` also deletes the match's rounds and throws. The admin delete for `events` and `matches` does the same.

**Rosters:** adding, removing and marking players late are single conditional updates, so two devices editing one roster cannot overwrite each other. Arena assignment (`PUT /event/{id}/arenas`) runs under a short Redis lock so two groups cannot claim the same arena.

## API Overview

### Auth — `/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | No | Register with an invite token |
| `POST` | `/auth/login` | No | Login, returns bearer token |
| `POST` | `/auth/logout` | Yes | Invalidate current token |
| `GET` | `/auth/user` | Yes | Get current user info |

Login and register expect `credentials` as a base64-encoded `username:password` string.

### Events — `/event`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/event` | Yes | Create an event |
| `GET` | `/event/{event_id}` | No | Get event by ID |
| `DELETE` | `/event/{event_id}` | Yes | Delete event |
| `POST` | `/event/{event_id}/lock` | Yes | Lock event |
| `POST` | `/event/{event_id}/unlock` | Yes | Unlock event |
| `POST` | `/event/{event_id}/finish` | Yes | Mark event as finished |
| `PUT` | `/event/{event_id}/type` | Yes | Set the event type (`standard` or `tournament`); see [Event types](#event-types) |

### Matches — `/match`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/match` | Yes | Create a match |
| `GET` | `/match/{match_id}` | No | Get match by ID |
| `GET` | `/match/event/{event_id}` | No | List matches for an event |
| `DELETE` | `/match/{match_id}` | Yes | Delete match |
| `POST` | `/match/{match_id}/lock` | Yes | Lock match |
| `POST` | `/match/{match_id}/unlock` | Yes | Unlock match |
| `POST` | `/match/{match_id}/finish` | Yes | Mark match as finished |

### Rounds — `/round`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/round` | Yes | Create a round |
| `GET` | `/round/{round_id}` | No | Get round by ID |
| `GET` | `/round/match/{match_id}` | No | List rounds for a match |
| `DELETE` | `/round/{round_id}` | Yes | Delete round |
| `POST` | `/round/{round_id}/lock` | Yes | Lock round |
| `POST` | `/round/{round_id}/unlock` | Yes | Unlock round |

### Throws — `/throw`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/throw/submit` | Yes | Submit a throw |
| `GET` | `/throw/{throw_id}` | No | Get throw by ID |
| `GET` | `/throw/search` | No | Search throws by player/round/match/event/venue |
| `DELETE` | `/throw/{throw_id}` | Yes | Delete throw |

### Venue and lanes

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/venue` | No | Static floor layout: `{"venue", "arenas": [{"arena_id", "name", "color", "text_color", "lanes": [{"lane_id", "label"}]}]}` |
| `GET` | `/lanes` | Yes | Live lane board: arenas with the group on each, plus waiting groups |
| `PUT` | `/event/{event_id}/arenas` | Yes | Put a group on one or more arenas |

### Players — `/player`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/player` | Yes | Create a player |
| `GET` | `/player` | No | List all players |
| `GET` | `/player/{player_id}` | No | Get player by ID |
| `DELETE` | `/player/{player_id}` | Yes | Delete player |

## Admin Panel

A browser-based admin interface is available at `/admin/login`. Requires a user account with `is_admin: true`.

To create an initial admin user:

```bash
python create_admin_user.py --username admin --email admin@example.com
# Use --insert --mongo-uri <uri> to write directly to the database
```

## Code Layout

- `app/routes/` parses input, calls a service or repository, and turns errors into HTTP responses. Services raise the domain errors in `app/services/errors.py`; `app/routes/errors.py` maps them to status codes.
- `app/services/` holds the logic: `tournament.py` (pure pairing, standings, brackets), `event_stages.py` (swiss schedule, late entries, standings and bracket for an event), `match_guards.py` (checks before scoring a match), `cascade.py` (deleting an event or match with its children), `lanes.py` (lane board, arena assignment, venue layout).
- `app/repositories/` talks to MongoDB, one class per collection; `documents.py` is the single builder for new event and match documents.
- `app/settings.py` reads the environment; `app/db/mongo.py` defines `DB_NAME`.

## Running Tests and Lint

```bash
pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
```

Tests run against in-memory fakes (`app/tests/fakes.py`). The fake Mongo raises `UnsupportedQueryOperator` for any query or update operator it does not implement; add new operators there with real MongoDB semantics and a test in `app/tests/test_fakes.py`. Ruff is configured in `ruff.toml` (pyflakes, pycodestyle errors, isort, bugbear); formatting is not enforced.

The Docker image installs only `requirements.txt` and `.dockerignore` keeps `app/tests` out of it.

## License

AGPLv3 — see [LICENSE](../LICENSE). Venue use and commercial licensing: [LICENSING.md](../LICENSING.md).
