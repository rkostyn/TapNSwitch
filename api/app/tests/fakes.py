"""
In-memory fakes for MongoClient and RedisClient.
Used to replace real database connections in tests.
"""
import copy
import json
import re
import time
import uuid

# ---------------------------------------------------------------------------
# MongoDB query helpers
# ---------------------------------------------------------------------------

_MISSING = object()


class UnsupportedQueryOperator(NotImplementedError):
    """Raised when a query uses an operator the fake does not implement."""


def _get_path(doc, path: str):
    """Resolve a (possibly dotted) field path; returns _MISSING if absent."""
    cur = doc
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return _MISSING
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return _MISSING
    return cur


def _candidates(value):
    """Values a scalar condition is tested against: the value itself plus,
    for arrays, each element (MongoDB array-matching semantics)."""
    if isinstance(value, list):
        return [value, *value]
    return [value]


def _eq(value, target) -> bool:
    if isinstance(target, re.Pattern):
        return _regex_match(value, target)
    if target is None:
        # {field: None} matches missing fields, explicit nulls, and arrays containing null.
        return value is _MISSING or any(c is None for c in _candidates(value))
    if value is _MISSING:
        return False
    return any(c == target for c in _candidates(value))


def _regex_match(value, pattern: re.Pattern) -> bool:
    if value is _MISSING:
        return False
    return any(isinstance(c, str) and pattern.search(c) for c in _candidates(value))


def _compile_regex(pattern, options: str = "") -> re.Pattern:
    if isinstance(pattern, re.Pattern):
        if not options:
            return pattern
        pattern = pattern.pattern
    flags = 0
    for opt in options:
        if opt == "i":
            flags |= re.IGNORECASE
        elif opt == "m":
            flags |= re.MULTILINE
        elif opt == "s":
            flags |= re.DOTALL
        elif opt == "x":
            flags |= re.VERBOSE
        else:
            raise UnsupportedQueryOperator(f"Unsupported $regex option: {opt!r}")
    return re.compile(pattern, flags)


def _compare(value, target, op) -> bool:
    if value is _MISSING or target is None:
        return False
    for c in _candidates(value):
        if c is None or isinstance(c, list):
            continue
        try:
            if op(c, target):
                return True
        except TypeError:
            # MongoDB only compares values of the same BSON type bracket.
            continue
    return False


_COMPARATORS = {
    "$gt": lambda a, b: a > b,
    "$gte": lambda a, b: a >= b,
    "$lt": lambda a, b: a < b,
    "$lte": lambda a, b: a <= b,
}


def _is_operator_expr(value) -> bool:
    return isinstance(value, dict) and bool(value) and all(
        isinstance(k, str) and k.startswith("$") for k in value
    )


def _matches_condition(value, cond: dict) -> bool:
    for op, op_val in cond.items():
        if op == "$eq":
            ok = _eq(value, op_val)
        elif op == "$ne":
            ok = not _eq(value, op_val)
        elif op == "$in":
            ok = any(_eq(value, t) for t in op_val)
        elif op == "$nin":
            ok = not any(_eq(value, t) for t in op_val)
        elif op in _COMPARATORS:
            ok = _compare(value, op_val, _COMPARATORS[op])
        elif op == "$size":
            ok = isinstance(value, list) and len(value) == op_val
        elif op == "$exists":
            ok = (value is not _MISSING) == bool(op_val)
        elif op == "$regex":
            ok = _regex_match(value, _compile_regex(op_val, cond.get("$options", "")))
        elif op == "$options":
            if "$regex" not in cond:
                raise UnsupportedQueryOperator("$options without $regex")
            ok = True
        elif op == "$not":
            if isinstance(op_val, re.Pattern):
                ok = not _regex_match(value, op_val)
            elif _is_operator_expr(op_val):
                ok = not _matches_condition(value, op_val)
            else:
                raise UnsupportedQueryOperator("$not requires an operator expression or regex")
        else:
            raise UnsupportedQueryOperator(f"Fake Mongo does not implement query operator {op!r}")
        if not ok:
            return False
    return True


def _matches_filter(doc: dict, filter_query: dict) -> bool:
    """Evaluate a MongoDB query filter against a document.

    Implements the subset of the query language the app uses, with real
    MongoDB semantics. Any operator not implemented raises
    UnsupportedQueryOperator rather than silently not matching.
    """
    if not filter_query:
        return True
    for key, value in filter_query.items():
        if key == "$and":
            if not all(_matches_filter(doc, sub) for sub in value):
                return False
        elif key == "$or":
            if not any(_matches_filter(doc, sub) for sub in value):
                return False
        elif key == "$nor":
            if any(_matches_filter(doc, sub) for sub in value):
                return False
        elif key.startswith("$"):
            raise UnsupportedQueryOperator(f"Fake Mongo does not implement top-level operator {key!r}")
        else:
            field_value = _get_path(doc, key)
            if _is_operator_expr(value):
                if not _matches_condition(field_value, value):
                    return False
            elif not _eq(field_value, value):
                return False
    return True


class FakeWriteError(Exception):
    """Stands in for pymongo's WriteError on an update real MongoDB rejects."""


def _array_field(doc: dict, key: str, op: str) -> list:
    """The array at ``key``, created empty if missing; non-arrays are an error,
    as in MongoDB."""
    if "." in key:
        raise UnsupportedQueryOperator(f"Fake Mongo does not implement dotted paths in {op}")
    if key not in doc:
        doc[key] = []
    if not isinstance(doc[key], list):
        raise FakeWriteError(f"Cannot apply {op} to non-array field {key!r}")
    return doc[key]


def _each(value) -> list:
    if isinstance(value, dict) and "$each" in value:
        if set(value) != {"$each"}:
            raise UnsupportedQueryOperator(f"Unsupported modifiers: {sorted(value)}")
        return list(value["$each"])
    return [value]


def _pull_matches(element, condition) -> bool:
    if _is_operator_expr(condition):
        return _matches_condition(element, condition)
    if isinstance(condition, dict):
        # A query on embedded document fields.
        return isinstance(element, dict) and _matches_filter(element, condition)
    return element == condition


def _apply_update(doc: dict, update: dict) -> dict:
    """Apply update operators to ``doc`` in place with MongoDB semantics:
    all-or-nothing, one operator per field, unknown operators raise."""
    seen: set[str] = set()
    for fields in update.values():
        for key in fields:
            if key in seen:
                raise FakeWriteError(f"Updating the path {key!r} would create a conflict")
            seen.add(key)
    staged = _apply_update_ops(copy.deepcopy(doc), update)
    doc.clear()
    doc.update(staged)
    return doc


def _apply_update_ops(doc: dict, update: dict) -> dict:
    for op, fields in update.items():
        if op == "$set":
            for k, v in fields.items():
                doc[k] = copy.deepcopy(v)
        elif op == "$addToSet":
            for k, v in fields.items():
                arr = _array_field(doc, k, op)
                for item in _each(v):
                    if item not in arr:
                        arr.append(copy.deepcopy(item))
        elif op == "$push":
            for k, v in fields.items():
                _array_field(doc, k, op).extend(copy.deepcopy(_each(v)))
        elif op == "$pull":
            for k, cond in fields.items():
                if k not in doc:
                    continue
                arr = _array_field(doc, k, op)
                arr[:] = [e for e in arr if not _pull_matches(e, cond)]
        else:
            raise UnsupportedQueryOperator(f"Fake Mongo does not implement update operator {op!r}")
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
            raise StopAsyncIteration from None

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
        # pymongo returns the document as it was before the update unless
        # return_document=ReturnDocument.AFTER (which is True).
        for doc in self._docs:
            if _matches_filter(doc, filter_query):
                before = copy.deepcopy(doc)
                _apply_update(doc, update)
                result = doc if return_document else before
                return _apply_projection(copy.deepcopy(result), projection)
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

    async def create_index(self, keys, unique=False, expireAfterSeconds=None):
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

    async def create_index(self, db_name: str, collection_name: str, keys: list, unique: bool = False,
                           expire_after_seconds: int | None = None):
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

    async def incr_with_expire(self, key: str, window: int) -> int:
        if self._expired(key):
            self._evict(key)
        self._counters[key] = self._counters.get(key, 0) + 1
        if self._counters[key] == 1:
            self._expires[key] = time.monotonic() + window
        return self._counters[key]

    async def expire(self, key: str, seconds: int):
        if key in self._store or key in self._counters:
            self._expires[key] = time.monotonic() + seconds

    async def acquire_lock(self, key: str, ttl_seconds: int):
        if self._expired(key):
            self._evict(key)
        if key in self._store:
            return None
        token = uuid.uuid4().hex
        self._store[key] = token
        self._expires[key] = time.monotonic() + ttl_seconds
        return token

    async def release_lock(self, key: str, token: str):
        if self._store.get(key) == token:
            self._evict(key)

    async def delete(self, key: str):
        self._store.pop(key, None)
        self._counters.pop(key, None)
        self._expires.pop(key, None)

    async def close(self):
        pass
