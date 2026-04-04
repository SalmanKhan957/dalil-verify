from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_TOKEN_SKEW_SECONDS = 60


@dataclass(frozen=True)
class QuranFoundationSettings:
    environment: str
    client_id: str
    client_secret: str
    auth_base_url: str
    api_base_url: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    token_skew_seconds: int = DEFAULT_TOKEN_SKEW_SECONDS

    @classmethod
    def from_env(cls) -> "QuranFoundationSettings":
        environment = os.getenv("QF_ENV", "preprod").strip().lower()
        if environment not in {"preprod", "production"}:
            raise ValueError("QF_ENV must be either 'preprod' or 'production'.")

        client_id = os.getenv("QF_CLIENT_ID", "").strip()
        client_secret = os.getenv("QF_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            raise ValueError("QF_CLIENT_ID and QF_CLIENT_SECRET must be set.")

        auth_base_url = os.getenv("QF_AUTH_BASE_URL", _default_auth_base_url(environment)).rstrip("/")
        api_base_url = os.getenv("QF_API_BASE_URL", _default_api_base_url(environment)).rstrip("/")
        timeout_seconds = float(os.getenv("QF_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
        token_skew_seconds = int(os.getenv("QF_TOKEN_SKEW_SECONDS", DEFAULT_TOKEN_SKEW_SECONDS))

        return cls(
            environment=environment,
            client_id=client_id,
            client_secret=client_secret,
            auth_base_url=auth_base_url,
            api_base_url=api_base_url,
            timeout_seconds=timeout_seconds,
            token_skew_seconds=token_skew_seconds,
        )

    def token_url(self) -> str:
        return f"{self.auth_base_url}/oauth2/token"

    def content_api_base(self) -> str:
        return f"{self.api_base_url}/content/api/v4"



def _default_auth_base_url(environment: str) -> str:
    if environment == "production":
        return "https://oauth2.quran.foundation"
    return "https://prelive-oauth2.quran.foundation"



def _default_api_base_url(environment: str) -> str:
    if environment == "production":
        return "https://apis.quran.foundation"
    return "https://apis-prelive.quran.foundation"
