from __future__ import annotations

from infrastructure.clients.quran_foundation.client import QuranFoundationContentClient
from infrastructure.clients.quran_foundation.models import TafsirResource


class QuranFoundationResourcesAPI:
    def __init__(self, content_client: QuranFoundationContentClient) -> None:
        self.content_client = content_client

    def list_tafsirs(self, *, language: str = "en") -> list[TafsirResource]:
        payload = self.content_client.get_json(
            "/resources/tafsirs",
            params={"language": language},
        )
        items = payload.get("tafsirs") or []
        return [TafsirResource.from_api(item) for item in items]
