# Tests

Pytest test suite using in-memory fakes for MongoDB and Redis — no real infrastructure required.

## Running

```bash
# From api/
python -m pytest app/tests/ -v
```

## Structure

| File | Covers |
|---|---|
| `conftest.py` | `client` fixture (TestClient), fake dependency overrides |
| `fakes.py` | `FakeMongoClient`, `FakeCollection`, `FakeRedisClient` |
| `test_main.py` | Startup check, healthz, security headers, X-Request-ID middleware, CORS |
| `test_auth_routes.py` | Register, login, logout, token lifecycle, registration token not consumed on failure |
| `test_admin_routes.py` | Admin login/logout, CRUD pages, PATCH allowlist enforcement |
| `test_event_routes.py` | Event CRUD, lock/unlock/finish, input validation |
| `test_match_routes.py` | Match CRUD, lock/unlock/finish, input validation |
| `test_round_routes.py` | Round CRUD, lock/unlock, input validation |
| `test_throw_routes.py` | Throw submit/search/delete, server-side ID/timestamp assignment |
| `test_throw.py` | Throw model unit tests |
| `test_player_routes.py` | Player CRUD, duplicate name rejection, input validation |
| `test_user_repo.py` | UserRepository duplicate handling |
| `test_dependencies.py` | Rate limiting, token validation |
| `test_mongo.py` | MongoClient wrapper |
| `test_redis.py` | RedisClient wrapper, `incr_with_expire` atomicity |

## Fakes

`FakeMongoClient` and `FakeRedisClient` mirror the real client interfaces but store data in memory. They do **not** enforce MongoDB unique indexes — repositories that need uniqueness add an application-level `find_one` pre-check so tests catch duplicates correctly.
