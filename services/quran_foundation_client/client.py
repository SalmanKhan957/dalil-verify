from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from services.quran_foundation_client.auth import QuranFoundationTokenProvider
from services.quran_foundation_client.config import QuranFoundationSettings


@dataclass
class QuranFoundationContentClient:
    settings: QuranFoundationSettings
    token_provider: QuranFoundationTokenProvider
    client: httpx.Client

    @classmethod
    def from_settings(cls, settings: QuranFoundationSettings) -> "QuranFoundationContentClient":
        client = httpx.Client(timeout=settings.timeout_seconds)
        token_provider = QuranFoundationTokenProvider(settings=settings, client=client)
        return cls(settings=settings, token_provider=token_provider, client=client)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "QuranFoundationContentClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.get(
            f"{self.settings.content_api_base()}{path}",
            params=params,
            headers=self._auth_headers(force_refresh=False),
        )
        if response.status_code == 401:
            self.token_provider.clear()
            response = self.client.get(
                f"{self.settings.content_api_base()}{path}",
                params=params,
                headers=self._auth_headers(force_refresh=True),
            )
        response.raise_for_status()
        return response.json()

    def _auth_headers(self, *, force_refresh: bool) -> dict[str, str]:
        return {
            "x-auth-token": self.token_provider.get_access_token(force_refresh=force_refresh),
            "x-client-id": self.settings.client_id,
        }
