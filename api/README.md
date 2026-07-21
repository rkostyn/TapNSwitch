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
- **Database:** MongoDB (via Motor async driver)
- **Cache / Sessions:** Redis
- **Auth:** Bearer tokens (stored as SHA-256 hashes in Redis, TTL 1 hour)

## Environment Variables

### Required

| Variable | Description |
|---|---|
| `MONGODB_URI` | Full MongoDB connection URI, e.g. `mongodb://user:pass@host:27017/admin?replicaSet=rs0&tls=true` |
| `REDIS_URI` | Full Redis connection URI, e.g. `redis://localhost:6379/0` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `ENV` | — | Set to `production` to disable API docs |
| `APP_NAME` | — | Application name shown in OpenAPI UI |
| `FORWARDED_ALLOW_IPS` | — | Trusted proxy IPs for `X-Forwarded-For` / `CF-Connecting-IP` handling |

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

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

## Running Tests

```bash
python -m pytest app/tests/ -v
```

## License

AGPLv3 — see [LICENSE](../LICENSE). Venue use and commercial licensing: [LICENSING.md](../LICENSING.md).
