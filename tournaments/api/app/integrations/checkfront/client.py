import os
from typing import Any

import httpx

from app.integrations.checkfront.parser import iter_checkfront_index_entries
from app.logger import get_logger

logger = get_logger(__name__)


class CheckfrontApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class CheckfrontApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        api_secret: str,
        client_ip: str = "127.0.0.1",
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = (api_key, api_secret)
        self._client_ip = client_ip

    @classmethod
    def from_env(cls) -> "CheckfrontApiClient | None":
        base_url = (os.getenv("CHECKFRONT_API_URL") or "").strip().rstrip("/")
        api_key = (os.getenv("CHECKFRONT_API_KEY") or "").strip()
        api_secret = (os.getenv("CHECKFRONT_API_SECRET") or "").strip()
        if not base_url or not api_key or not api_secret:
            return None
        client_ip = (os.getenv("CHECKFRONT_API_CLIENT_IP") or "127.0.0.1").strip()
        return cls(
            base_url=base_url,
            api_key=api_key,
            api_secret=api_secret,
            client_ip=client_ip,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "X-Forwarded-For": self._client_ip,
        }

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params=params,
                auth=self._auth,
                headers=self._headers(),
            )
        if response.status_code >= 400:
            logger.warning("Checkfront API %s failed: %s", path, response.status_code)
            raise CheckfrontApiError(
                f"Checkfront API request failed ({response.status_code})",
                status_code=response.status_code,
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise CheckfrontApiError("Checkfront API returned an unexpected response")
        request_meta = payload.get("request")
        if isinstance(request_meta, dict) and request_meta.get("status") not in (None, "OK"):
            raise CheckfrontApiError(f"Checkfront API error: {request_meta.get('status')}")
        return payload

    async def list_bookings(
        self,
        *,
        start_date: str = "today",
        status_id: str | None = None,
    ) -> list[dict[str, Any]]:
        page = 1
        entries: list[dict[str, Any]] = []
        while True:
            params: dict[str, Any] = {"start_date": start_date, "page": page, "limit": 100}
            if status_id:
                params["status_id"] = status_id
            payload = await self._get("booking/index", params=params)
            entries.extend(iter_checkfront_index_entries(payload))
            request_meta = payload.get("request")
            if not isinstance(request_meta, dict):
                break
            pages = int(request_meta.get("pages") or 1)
            if page >= pages:
                break
            page += 1
        return entries

    async def get_booking(self, booking_id: str) -> dict[str, Any]:
        return await self._get(f"booking/{booking_id}")
