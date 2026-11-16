"""Domain errors raised by services.

Each carries the ``detail`` the API returns; ``app.routes.errors`` maps the
class to an HTTP status. Services never import FastAPI.
"""
from typing import Any


class DomainError(Exception):
    def __init__(self, detail: Any):
        super().__init__(detail if isinstance(detail, str) else repr(detail))
        self.detail = detail


class NotFoundError(DomainError):
    """The thing asked for does not exist (404)."""


class ConflictError(DomainError):
    """The request clashes with the current state (409)."""


class LockedError(DomainError):
    """Finished or locked by someone else (423)."""


class ForbiddenError(DomainError):
    """Held by another caller (403)."""
