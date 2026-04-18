# DB

Database clients and index definitions.

## Files

### `mongo.py`

Thin async wrapper around Motor. Exposes `get_database()`, `create_index()`, `ping()`, and `close()`. Injected into routes via `dependencies.get_mongo_client`.

### `redis.py`

Thin async wrapper around `redis.asyncio`. Key methods:

| Method | Purpose |
|---|---|
| `get` / `set` / `delete` | Standard KV ops |
| `incr_with_expire(key, window)` | Atomic INCR + EXPIRE via Lua script. Used for rate limiting to avoid the INCR/EXPIRE race. |
| `ping` / `close` | Health check and cleanup |

Injected via `dependencies.get_redis_client`.

### `indexes.json`

MongoDB index definitions applied at startup. Each entry specifies `db`, `collection`, `keys`, and optionally `unique: true`.

Current unique indexes:

- `users.user_name`
- `users.email`
- `registration_tokens.token`
