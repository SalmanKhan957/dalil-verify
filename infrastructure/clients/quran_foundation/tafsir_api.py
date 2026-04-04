from __future__ import annotations

from typing import Iterator

import httpx

from infrastructure.clients.quran_foundation.client import QuranFoundationContentClient
from infrastructure.clients.quran_foundation.models import ApiPagination, TafsirAyahEntry


class TafsirChapterNotFoundError(Exception):
    def __init__(self, *, resource_id: int, chapter_number: int) -> None:
        self.resource_id = resource_id
        self.chapter_number = chapter_number
        super().__init__(
            f"Tafsir resource {resource_id} does not have content for chapter {chapter_number}."
        )


class QuranFoundationTafsirAPI:
    def __init__(self, content_client: QuranFoundationContentClient) -> None:
        self.content_client = content_client

    def get_surah_tafsirs(
        self,
        *,
        resource_id: int,
        chapter_number: int,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[TafsirAyahEntry], ApiPagination | None]:
        try:
            payload = self.content_client.get_json(
                f"/tafsirs/{resource_id}/by_chapter/{chapter_number}",
                params={"page": page, "per_page": per_page},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise TafsirChapterNotFoundError(
                    resource_id=resource_id,
                    chapter_number=chapter_number,
                ) from exc
            raise

        items = [TafsirAyahEntry.from_api(item) for item in (payload.get("tafsirs") or [])]
        pagination = ApiPagination.from_api(payload.get("pagination"))
        return items, pagination

    def iter_surah_tafsirs(
        self,
        *,
        resource_id: int,
        chapter_number: int,
        per_page: int = 50,
    ) -> Iterator[TafsirAyahEntry]:
        page = 1
        while True:
            items, pagination = self.get_surah_tafsirs(
                resource_id=resource_id,
                chapter_number=chapter_number,
                page=page,
                per_page=per_page,
            )
            for item in items:
                yield item
            if not pagination or pagination.next_page is None:
                break
            page = pagination.next_page
