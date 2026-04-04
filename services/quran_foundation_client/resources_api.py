from __future__ import annotations

from services.quran_foundation_client.client import QuranFoundationContentClient
from services.quran_foundation_client.models import TafsirResource


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
