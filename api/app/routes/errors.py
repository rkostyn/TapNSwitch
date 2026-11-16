"""Map service-layer domain errors to HTTP responses."""
from fastapi import Request
from fastapi.responses import JSONResponse

from app.services.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    LockedError,
    NotFoundError,
)

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    LockedError: 423,
    ForbiddenError: 403,
}


def status_for(exc: DomainError) -> int:
    for cls in type(exc).__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return 400


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Same body shape as ``HTTPException``: ``{"detail": ...}``."""
    return JSONResponse(status_code=status_for(exc), content={"detail": exc.detail})
