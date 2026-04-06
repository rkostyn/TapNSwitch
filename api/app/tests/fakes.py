"""
In-memory fakes for MongoClient and RedisClient.
Used to replace real database connections in tests.
"""
import copy
import json
import time


# ---------------------------------------------------------------------------
# MongoDB query helpers
# ---------------------------------------------------------------------------

def _matches_filter(doc: dict, filter_query: dict) -> bool:
    if not filter_query:
        return True
    for key, value in filter_query.items():
        if key == "$or":
            if not any(_matches_filter(doc, sub) for sub in value):
                return False
        elif isinstance(value, dict):
            for op, op_val in value.items():
                if op == "$in":
                    if doc.get(key) not in op_val:
                        return False
                else:
                    return False
        else:
            if doc.get(key) != value:
                return False
    return True


def _apply_update(doc: dict, update: dict) -> dict:
    if "$set" in update:
        for k, v in update["$set"].items():
            doc[k] = v
    return doc


def _apply_projection(doc: dict, projection: dict | None) -> dict:
    if not projection:
        return doc
    non_id = {k: v for k, v in projection.items() if k != "_id"}
    if not non_id or all(v == 0 for v in non_id.values()):
        # Exclusion mode
        return {k: v for k, v in doc.items() if projection.get(k, 1) != 0}
    else:
        # Inclusion mode
        result = {k: v for k, v in doc.items() if projection.get(k) == 1}
        if projection.get("_id", 1) != 0 and "_id" in doc:
            result["_id"] = doc["_id"]
        return result


# ---------------------------------------------------------------------------
# Cursor
# ---------------------------------------------------------------------------

class FakeCursor:
    def __init__(self, docs: list):
        self._docs = list(docs)
        self._sort_field = None
        self._sort_dir = 1
        self._limit_n = None

    def sort(self, field, direction=1):
        self._sort_field = field
        self._sort_dir = direction
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def _get_docs(self):
        docs = list(self._docs)
        if self._sort_field:
            field = self._sort_field
            docs.sort(
                key=lambda d: (d.get(field) is None, d.get(field) if d.get(field) is not None else 0),
                reverse=(self._sort_dir == -1),
            )
        if self._limit_n is not None:
            docs = docs[:self._limit_n]
        return docs

    def __aiter__(self):
        self._iter = iter(self._get_docs())
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length=None):
        docs = self._get_docs()
        return docs[:length] if length is not None else docs


# ---------------------------------------------------------------------------
# Result stubs
# ---------------------------------------------------------------------------

class _InsertOneResult:
    inserted_id = "fake_id"


class _InsertManyResult:
    def __init__(self, n):
        self.inserted_ids = ["fake_id"] * n


class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class _DeleteResult:
    def __init__(self, count):
        self.deleted_count = count


# ---------------------------------------------------------------------------
# FakeCollection
# ---------------------------------------------------------------------------

class FakeCollection:
    def __init__(self, name: str = ""):
        self.name = name
        self._docs: list[dict] = []

    async def find_one(self, filter_query=None, projection=None):
        for doc in self._docs:
            if _matches_filter(doc, filter_query or {}):
                return _apply_projection(copy.deepcopy(doc), projection)
        return None

    def find(self, filter_query=None, projection=None):
        matched = [
            _apply_projection(copy.deepcopy(doc), projection)
            for doc in self._docs
            if _matches_filter(doc, filter_query or {})
        ]
        return FakeCursor(matched)

    async def insert_one(self, doc):
        self._docs.append(copy.deepcopy(doc))
        return _InsertOneResult()

    async def insert_many(self, docs):
        for doc in docs:
            self._docs.append(copy.deepcopy(doc))
        return _InsertManyResult(len(docs))

    async def find_one_and_delete(self, filter_query):
        for i, doc in enumerate(self._docs):
            if _matches_filter(doc, filter_query):
                return self._docs.pop(i)
        return None

    async def find_one_and_update(self, filter_query, update, projection=None, return_document=None):
        for doc in self._docs:
            if _matches_filter(doc, filter_query):
                _apply_update(doc, update)
                return _apply_projection(copy.deepcopy(doc), projection)
        return None

    async def update_one(self, filter_query, update):
        for doc in self._docs:
            if _matches_filter(doc, filter_query):
                _apply_update(doc, update)
                return _UpdateResult(1, 1)
        return _UpdateResult(0, 0)

    async def delete_one(self, filter_query):
        for i, doc in enumerate(self._docs):
            if _matches_filter(doc, filter_query):
                self._docs.pop(i)
                return _DeleteResult(1)
        return _DeleteResult(0)

    async def delete_many(self, filter_query):
        before = len(self._docs)
        self._docs = [d for d in self._docs if not _matches_filter(d, filter_query)]
        return _DeleteResult(before - len(self._docs))

    async def aggregate(self, pipeline):
        docs = [copy.deepcopy(d) for d in self._docs]
        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if _matches_filter(d, stage["$match"])]
            elif "$project" in stage:
                docs = [_apply_projection(d, stage["$project"]) for d in docs]
        return FakeCursor(docs)

    async def create_index(self, keys, unique=False):
        pass


# ---------------------------------------------------------------------------
# FakeMongoClient
# ---------------------------------------------------------------------------

class FakeMongoClient:
    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def _get_or_create(self, db: str, collection: str) -> FakeCollection:
        key = f"{db}:{collection}"
        if key not in self._collections:
            self._collections[key] = FakeCollection(name=collection)
        return self._collections[key]

    async def get_database(self, db_name: str):
        # Return a thin proxy so callers can do db["collection"]
        return _FakeDatabase(self, db_name)

    async def get_collection(self, db_name: str, collection_name: str) -> FakeCollection:
        return self._get_or_create(db_name, collection_name)

    async def ping(self) -> bool:
        return True

    async def close(self):
        pass

    async def drop_database(self, db_name: str):
        keys = [k for k in self._collections if k.startswith(f"{db_name}:")]
        for k in keys:
            del self._collections[k]

    async def drop_collection(self, db_name: str, collection_name: str):
        key = f"{db_name}:{collection_name}"
        if key in self._collections:
            self._collections[key]._docs.clear()

    async def create_index(self, db_name: str, collection_name: str, keys: list, unique: bool = False):
        pass


class _FakeDatabase:
    """Minimal proxy so auth code can do db['registration_tokens']."""
    def __init__(self, client: FakeMongoClient, db_name: str):
        self._client = client
        self._db_name = db_name

    def __getitem__(self, collection_name: str) -> FakeCollection:
        return self._client._get_or_create(self._db_name, collection_name)

    @property
    def name(self):
        return self._db_name


# ---------------------------------------------------------------------------
# FakeRedisClient
# ---------------------------------------------------------------------------

class FakeRedisClient:
    def __init__(self):
        self._store: dict[str, str] = {}     # json-serialised values (set/get)
        self._counters: dict[str, int] = {}  # integer counters (incr)
        self._expires: dict[str, float] = {} # monotonic expiry timestamps

    def _expired(self, key: str) -> bool:
        exp = self._expires.get(key)
        return exp is not None and time.monotonic() > exp

    def _evict(self, key: str):
        self._store.pop(key, None)
        self._counters.pop(key, None)
        self._expires.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value, expire: int = None):
        self._store[key] = json.dumps(value)
        if expire is not None:
            self._expires[key] = time.monotonic() + expire
        else:
            self._expires.pop(key, None)

    async def get(self, key: str):
        if self._expired(key):
            self._evict(key)
            return None
        v = self._store.get(key)
        return json.loads(v) if v is not None else None

    async def incr(self, key: str) -> int:
        if self._expired(key):
            self._evict(key)
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, seconds: int):
        if key in self._store or key in self._counters:
            self._expires[key] = time.monotonic() + seconds

    async def delete(self, key: str):
        self._store.pop(key, None)
        self._counters.pop(key, None)
        self._expires.pop(key, None)

    async def close(self):
        pass
