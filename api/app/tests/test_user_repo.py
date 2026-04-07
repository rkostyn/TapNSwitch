"""
Unit tests for UserRepository against the in-memory FakeMongoClient.
A fresh FakeMongoClient is used per-test so tests are isolated.
"""
import pytest

from app.models.user import UserCreate, UserDelete
from app.repositories.user_repository import UserRepository
from app.tests.fakes import FakeMongoClient


@pytest.fixture
def fake_mongo():
    return FakeMongoClient()


@pytest.fixture
def repo(fake_mongo):
    return UserRepository(fake_mongo)


async def _create_testuser(repo):
    return await repo.create_user(UserCreate(
        user_name="testuser",
        email="test-user@yeetbox.net",
        password="testpassword",
        registration_token="dummy",
    ))


async def test_create_and_get_user(repo):
    user = await _create_testuser(repo)
    assert user.user_name == "testuser"
    assert user.email == "test-user@yeetbox.net"
    assert user.user_id

    fetched = await repo.get_user("testuser")
    assert fetched is not None
    assert fetched.user_name == "testuser"
    assert fetched.created_at is not None


async def test_verify_user_correct_password(repo):
    await _create_testuser(repo)
    assert await repo.verify_user("testuser", "testpassword") is True


async def test_verify_user_wrong_password(repo):
    await _create_testuser(repo)
    assert await repo.verify_user("testuser", "wrongpassword") is False


async def test_verify_user_nonexistent(repo):
    assert await repo.verify_user("doesnotexist", "anypassword") is False


async def test_create_user_duplicate_username(repo):
    await _create_testuser(repo)
    with pytest.raises(ValueError, match="already exists"):
        await repo.create_user(UserCreate(
            user_name="testuser",
            email="other@example.com",
            password="somepassword123",
            registration_token="dummy",
        ))


async def test_create_user_duplicate_email(repo):
    await _create_testuser(repo)
    with pytest.raises(ValueError, match="already exists"):
        await repo.create_user(UserCreate(
            user_name="otheruser",
            email="test-user@yeetbox.net",
            password="somepassword123",
            registration_token="dummy",
        ))


async def test_get_user_nonexistent(repo):
    assert await repo.get_user("nosuchuser") is None


async def test_delete_user(repo):
    user = await _create_testuser(repo)
    result = await repo.delete_user(UserDelete(
        user_id=user.user_id,
        user_name="testuser",
        email="test-user@yeetbox.net",
    ))
    assert result is True
    assert await repo.get_user("testuser") is None


async def test_delete_user_not_found(repo):
    result = await repo.delete_user(UserDelete(
        user_id="does-not-exist",
        user_name="ghost",
        email="ghost@example.com",
    ))
    assert result is False


async def test_is_admin_false_by_default(repo):
    await _create_testuser(repo)
    assert await repo.is_admin("testuser") is False
