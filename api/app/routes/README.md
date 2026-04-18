# Routes

FastAPI routers. Each file owns one resource prefix.

| File | Prefix | Notes |
|---|---|---|
| `auth.py` | `/auth` | Register, login, logout, current user. Rate-limited. |
| `event.py` | `/event` | CRUD + lock/unlock/finish. |
| `match.py` | `/match` | CRUD + lock/unlock/finish. Scoped to an event. |
| `round.py` | `/round` | CRUD + lock/unlock. Scoped to a match. |
| `throw.py` | `/throw` | Submit, search, delete. Client-supplied `throw_id` and `timestamp` are ignored. |
| `player.py` | `/player` | CRUD. Player names must be unique. |
| `admin.py` | `/admin` | Browser-based admin panel. Cookie auth (separate from bearer tokens). |

## Auth model

Most write routes require a `Bearer` token in the `Authorization` header. Tokens are stored as SHA-256 hashes in Redis with a 1-hour TTL. Read routes (`GET`) are unauthenticated.

The admin panel uses a separate session cookie issued at `/admin/login`.

## Locking

Events and matches support optimistic locking. A `POST /{resource}/{id}/lock` call records the locking user. While locked, only that user (or an admin) can write. Unlock with `POST /{resource}/{id}/unlock`.

## CORS

Allowed origins are configured via the `CORS_ORIGINS` environment variable (comma-separated). Falls back to `*` when unset.
