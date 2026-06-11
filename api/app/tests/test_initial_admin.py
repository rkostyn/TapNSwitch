import os
from unittest.mock import patch

import pytest

from app.bootstrap.initial_admin import ensure_initial_admin
from app.repositories.user_repository import UserRepository
from app.tests.fakes import FakeMongoClient


@pytest.mark.asyncio
async def test_ensure_initial_admin_skips_without_password():
    mongo = FakeMongoClient()
    removes = [
        "INITIAL_ADMIN_PASSWORD",
        "INITIAL_ADMIN_USERNAME",
        "INITIAL_ADMIN_EMAIL",
    ]
    env = {k: v for k, v in os.environ.items() if k not in removes}
    with patch.dict(os.environ, env, clear=True):
        await ensure_initial_admin(mongo)
    users = mongo._get_or_create("axes", "users")
    assert users._docs == []


@pytest.mark.asyncio
async def test_ensure_initial_admin_creates_once():
    mongo = FakeMongoClient()
    env = {
        "INITIAL_ADMIN_PASSWORD": "bootstrap-secret",
        "INITIAL_ADMIN_USERNAME": "firstadmin",
        "INITIAL_ADMIN_EMAIL": "first@example.com",
    }
    with patch.dict(os.environ, env):
        await ensure_initial_admin(mongo)
        await ensure_initial_admin(mongo)

    users = mongo._get_or_create("axes", "users")
    assert len(users._docs) == 1
    assert users._docs[0]["user_name"] == "firstadmin"
    assert users._docs[0]["is_admin"] is True


@pytest.mark.asyncio
async def test_ensure_initial_admin_skips_when_admin_exists():
    mongo = FakeMongoClient()
    repo = UserRepository(mongo)
    await repo.create_user_admin("existing", "existing@example.com", "pw", is_admin=True)

    with patch.dict(
        os.environ,
        {
            "INITIAL_ADMIN_PASSWORD": "other-secret",
            "INITIAL_ADMIN_USERNAME": "other",
            "INITIAL_ADMIN_EMAIL": "other@example.com",
        },
    ):
        await ensure_initial_admin(mongo)

    users = mongo._get_or_create("axes", "users")
    assert len(users._docs) == 1
    assert users._docs[0]["user_name"] == "existing"
