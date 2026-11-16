"""Settings keep the semantics of the os.getenv calls they replaced."""
import pytest
from pydantic import ValidationError

from app.settings import DEFAULT_ACCEPT_STATUSES, get_settings

_VARS = [
    "LOG_LEVEL", "ENV", "APP_NAME", "CORS_ORIGINS",
    "INITIAL_ADMIN_PASSWORD", "INITIAL_ADMIN_USERNAME", "INITIAL_ADMIN_EMAIL",
    "CHECKFRONT_WEBHOOK_SECRET", "CHECKFRONT_API_URL", "CHECKFRONT_API_KEY",
    "CHECKFRONT_API_SECRET", "CHECKFRONT_API_CLIENT_IP", "CHECKFRONT_SYNC_INTERVAL_SECONDS",
    "CHECKFRONT_GROUP_MODE", "CHECKFRONT_PLAYER_FIELD_KEYS", "CHECKFRONT_ACCEPT_STATUSES",
    "CHECKFRONT_PULL_FETCH_DETAIL", "VENUE_TIMEZONE", "CHECKFRONT_TIMEZONE",
]


@pytest.fixture
def clean_env(monkeypatch):
    for name in _VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults(clean_env):
    s = get_settings()
    assert s.log_level == "INFO"
    assert not s.is_production
    assert s.app_name is None
    assert s.cors_origin_list == []
    assert s.initial_admin_password == ""
    assert s.initial_admin_username == "admin"
    assert s.initial_admin_email == "admin@local.dev"
    assert s.checkfront_api_client_ip == "127.0.0.1"
    assert s.checkfront_sync_interval_seconds == 0
    assert s.checkfront_group_mode == "session"
    assert s.player_field_key_list == []
    assert s.accept_status_set == set(DEFAULT_ACCEPT_STATUSES)
    assert s.checkfront_pull_fetch_detail is True
    assert not s.checkfront_api_configured
    assert str(s.venue_tz) == "America/New_York"


def test_values_are_read_at_call_time(clean_env):
    assert get_settings().checkfront_group_mode == "session"
    clean_env.setenv("CHECKFRONT_GROUP_MODE", "booking")
    assert get_settings().checkfront_group_mode == "booking"


def test_blank_and_whitespace_fall_back_to_defaults(clean_env):
    clean_env.setenv("INITIAL_ADMIN_USERNAME", "   ")
    clean_env.setenv("CHECKFRONT_SYNC_INTERVAL_SECONDS", "")
    clean_env.setenv("CHECKFRONT_ACCEPT_STATUSES", " ")
    s = get_settings()
    assert s.initial_admin_username == "admin"
    assert s.checkfront_sync_interval_seconds == 0
    assert s.accept_status_set == set(DEFAULT_ACCEPT_STATUSES)


def test_parsing(clean_env):
    clean_env.setenv("LOG_LEVEL", "debug")
    clean_env.setenv("ENV", "production")
    clean_env.setenv("CORS_ORIGINS", "https://a.test, ,https://b.test")
    clean_env.setenv("CHECKFRONT_GROUP_MODE", " Booking ")
    clean_env.setenv("CHECKFRONT_PLAYER_FIELD_KEYS", "thrower_names, participant_names,")
    clean_env.setenv("CHECKFRONT_ACCEPT_STATUSES", "paid, conf")
    clean_env.setenv("CHECKFRONT_SYNC_INTERVAL_SECONDS", " 300 ")
    clean_env.setenv("CHECKFRONT_API_URL", " https://x.test/api/ ")
    clean_env.setenv("CHECKFRONT_API_KEY", "k")
    clean_env.setenv("CHECKFRONT_API_SECRET", "s")
    s = get_settings()
    assert s.log_level == "DEBUG"
    assert s.is_production
    assert s.cors_origin_list == ["https://a.test", "https://b.test"]
    assert s.checkfront_group_mode == "booking"
    assert s.player_field_key_list == ["thrower_names", "participant_names"]
    assert s.accept_status_set == {"PAID", "CONF"}
    assert s.checkfront_sync_interval_seconds == 300
    assert s.checkfront_api_url == "https://x.test/api/"
    assert s.checkfront_api_configured


def test_unknown_group_mode_falls_back_to_session(clean_env):
    clean_env.setenv("CHECKFRONT_GROUP_MODE", "weekly")
    assert get_settings().checkfront_group_mode == "session"


@pytest.mark.parametrize("raw,expected", [
    ("0", False), ("false", False), ("NO", False),
    ("true", True), ("1", True), ("anything", True),
])
def test_fetch_detail(clean_env, raw, expected):
    clean_env.setenv("CHECKFRONT_PULL_FETCH_DETAIL", raw)
    assert get_settings().checkfront_pull_fetch_detail is expected


def test_timezone_fallback_order(clean_env):
    clean_env.setenv("CHECKFRONT_TIMEZONE", "America/Chicago")
    assert str(get_settings().venue_tz) == "America/Chicago"
    clean_env.setenv("VENUE_TIMEZONE", "America/Denver")
    assert str(get_settings().venue_tz) == "America/Denver"


def test_invalid_interval_raises(clean_env):
    clean_env.setenv("CHECKFRONT_SYNC_INTERVAL_SECONDS", "often")
    with pytest.raises(ValidationError):
        get_settings()
