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
| `MONGODB_URI` | Full MongoDB connection URI |
| `REDIS_URI` | Full Redis connection URI |

### Optional

| Variable | Default | Description |
|---|---|---|
| `ENV` | — | Set to `production` to disable API docs |
| `APP_NAME` | — | Application name shown in OpenAPI UI |
| `CORS_ORIGINS` | — | Comma-separated allowed origins. Falls back to `*` when unset. |
| `FORWARDED_ALLOW_IPS` | — | Trusted proxy IPs for `X-Forwarded-For` / `CF-Connecting-IP` handling |

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start dependencies
docker run -d -p 27017:27017 mongo
docker run -d -p 6379:6379 redis

export MONGODB_URI="mongodb://localhost:27017/admin"
export REDIS_URI="redis://localhost:6379/0"

uvicorn app.main:app --reload --port 8000
```

API docs (Swagger UI) will be available at `http://localhost:8000/`.

## Running Tests

```bash
python -m pytest app/tests/ -v
```

## Data Model

```
Event
└── Match (player_1 vs player_2, sequence number)
    └── Round
        └── Throw (player, points, clutch_called, is_premier, is_drop)
```

## Admin Panel

Available at `/admin/login`. Requires a user account with `is_admin: true`.

To create an initial admin user:

```bash
python create_admin_user.py --username admin --email admin@example.com
```

## Directory Docs

- [app/routes/](app/routes/README.md) — API routers, auth model, locking, CORS
- [app/models/](app/models/README.md) — Pydantic request/response models and validation rules
- [app/repositories/](app/repositories/README.md) — Data-access layer, duplicate handling
- [app/db/](app/db/README.md) — MongoDB and Redis clients, index definitions
- [app/tests/](app/tests/README.md) — Test suite structure and fakes

## License

GPLv3 — see [LICENSE](https://www.gnu.org/licenses/gpl-3.0.en.html).
