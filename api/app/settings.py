"""Every environment variable the API reads, in one place.

``get_settings()`` always reflects the current environment rather than an
import-time snapshot, so tests can switch values with ``monkeypatch.setenv``
and see them immediately. Building ``Settings`` costs ~0.5 ms, so the last
instance is reused for as long as ``os.environ`` is unchanged.

Conventions kept from the old scattered ``os.getenv`` calls:

* values are stripped, and an empty or whitespace-only value means "unset"
  (falls back to the default);
* lenient fields stay lenient: an unknown ``CHECKFRONT_GROUP_MODE`` falls back
  to ``session`` and ``CHECKFRONT_PULL_FETCH_DETAIL`` is true unless it is one
  of ``0``/``false``/``no``.
"""
import os
from zoneinfo import ZoneInfo

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# STOP/PREP are Checkfront's arrived / about-to-arrive statuses on the floor.
DEFAULT_ACCEPT_STATUSES = frozenset({"PAID", "CONF", "PEND", "HOLD", "WAIT", "STOP", "PREP"})
GROUP_MODES = frozenset({"booking", "session"})


def _csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore")

    # Connections. Optional here so importing the app never fails; the clients
    # raise KeyError on use when they are missing, as before.
    mongodb_uri: str | None = None
    redis_uri: str | None = None

    # App
    env: str | None = None
    app_name: str | None = None
    log_level: str = "INFO"
    cors_origins: str = ""

    # First admin, created on startup when no admin exists
    initial_admin_password: str = ""
    initial_admin_username: str = "admin"
    initial_admin_email: str = "admin@local.dev"

    # Checkfront
    checkfront_webhook_secret: str = ""
    checkfront_api_url: str = ""
    checkfront_api_key: str = ""
    checkfront_api_secret: str = ""
    checkfront_api_client_ip: str = "127.0.0.1"
    checkfront_sync_interval_seconds: int = 0
    checkfront_group_mode: str = "session"
    checkfront_player_field_keys: str = ""
    checkfront_accept_statuses: str = ""
    checkfront_pull_fetch_detail: bool = True

    # Venue timezone for "today" filters; CHECKFRONT_TIMEZONE is the legacy name.
    venue_timezone: str | None = None
    checkfront_timezone: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _strip_blank_to_default(cls, value, info: ValidationInfo):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return cls.model_fields[info.field_name].default
        return value

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("checkfront_group_mode")
    @classmethod
    def _group_mode(cls, value: str) -> str:
        value = value.lower()
        return value if value in GROUP_MODES else "session"

    @field_validator("checkfront_pull_fetch_detail", mode="before")
    @classmethod
    def _fetch_detail(cls, value) -> bool:
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no"}
        return bool(value)

    # Derived values -----------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return _csv(self.cors_origins)

    @property
    def player_field_key_list(self) -> list[str]:
        return _csv(self.checkfront_player_field_keys)

    @property
    def accept_status_set(self) -> set[str]:
        statuses = {part.upper() for part in _csv(self.checkfront_accept_statuses)}
        return statuses or set(DEFAULT_ACCEPT_STATUSES)

    @property
    def checkfront_api_configured(self) -> bool:
        return bool(self.checkfront_api_url and self.checkfront_api_key and self.checkfront_api_secret)

    @property
    def venue_tz(self) -> ZoneInfo:
        return ZoneInfo(self.venue_timezone or self.checkfront_timezone or "America/New_York")


_cached: tuple[tuple, Settings] | None = None


def get_settings() -> Settings:
    """Settings for the environment as it is right now.

    Rebuilt whenever anything in ``os.environ`` has changed since the last
    call; otherwise the previous instance is returned.
    """
    global _cached
    key = tuple(sorted(os.environ.items()))
    if _cached is None or _cached[0] != key:
        _cached = (key, Settings())
    return _cached[1]
