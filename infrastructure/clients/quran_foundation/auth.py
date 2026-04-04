from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from infrastructure.clients.quran_foundation.config import QuranFoundationSettings
from infrastructure.clients.quran_foundation.models import AccessToken


@dataclass
class QuranFoundationTokenProvider:
    settings: QuranFoundationSettings
    client: httpx.Client
    _cached_token: AccessToken | None = None

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        now = time.time()
        if not force_refresh and self._cached_token and not self._cached_token.is_expired(
            now_epoch=now,
            skew_seconds=self.settings.token_skew_seconds,
        ):
            return self._cached_token.token

        response = self.client.post(
            self.settings.token_url(),
            data={"grant_type": "client_credentials", "scope": "content"},
            auth=(self.settings.client_id, self.settings.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = response.json()

        expires_in = int(payload.get("expires_in") or 3600)
        access_token = str(payload["access_token"])
        token_type = str(payload.get("token_type") or "Bearer")
        scope = payload.get("scope")
        self._cached_token = AccessToken(
            token=access_token,
            expires_at_epoch=now + expires_in,
            token_type=token_type,
            scope=scope,
        )
        return self._cached_token.token

    def clear(self) -> None:
        self._cached_token = None
