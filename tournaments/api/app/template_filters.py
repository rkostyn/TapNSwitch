"""Custom Jinja2 template filters. Add new filters here and register them in templates.py."""

import jinja2
from datetime import datetime


def datetimeformat(value, fmt="%Y-%m-%d %H:%M:%S"):
    """Format a datetime object or ISO string."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(fmt)


@jinja2.pass_context
async def retrieve_x_latest(ctx, data_type: str, to_retrieve: int, sort_field: str):
    """
    Retrieve the X most recent documents from any collection, sorted descending by sort_field.

    Usage in templates (data_type is piped as the filter value):
        {{ "events" | retrieve_x_latest(5, "timestamp") }}
        {{ "throws" | retrieve_x_latest(10, "timestamp") }}

    Requires the template context to include `request` (standard in FastAPI routes).
    The mongo client is pulled from request.app.state.mongo_client.
    Returns a list of plain dicts with _id excluded.
    """
    request = ctx["request"]
    mongo_client = request.app.state.mongo_client
    collection = await mongo_client.get_collection("axes", data_type)
    cursor = collection.find({}, {"_id": 0}).sort(sort_field, -1).limit(to_retrieve)
    return [doc async for doc in cursor]


@jinja2.pass_context
async def find_related(ctx, value: str, collection: str, field: str, sort_field: str = "timestamp", limit: int = 100):
    """
    Fetch documents from a collection where field == value.

    Usage: doc.event_id | find_related("matches", "event_id")
    """
    if not value:
        return []
    request = ctx["request"]
    mongo_client = request.app.state.mongo_client
    col = await mongo_client.get_collection("axes", collection)
    cursor = col.find({field: value}, {"_id": 0}).sort(sort_field, -1).limit(limit)
    return [doc async for doc in cursor]


@jinja2.pass_context
async def find_player_matches(ctx, player_id: str, limit: int = 100):
    """
    Fetch matches where the player appears as either player_1_id or player_2_id.

    Usage: doc.player_id | find_player_matches()
    """
    if not player_id:
        return []
    request = ctx["request"]
    mongo_client = request.app.state.mongo_client
    col = await mongo_client.get_collection("axes", "matches")
    cursor = col.find(
        {"$or": [{"player_1_id": player_id}, {"player_2_id": player_id}]},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit)
    return [doc async for doc in cursor]
