from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AccessToken:
    token: str
    expires_at_epoch: float
    token_type: str = "Bearer"
    scope: str | None = None

    def is_expired(self, now_epoch: float, skew_seconds: int = 0) -> bool:
        return (self.expires_at_epoch - skew_seconds) <= now_epoch


@dataclass(frozen=True)
class TafsirResource:
    resource_id: int
    name: str
    author_name: str | None
    slug: str | None
    language_name: str | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "TafsirResource":
        return cls(
            resource_id=int(payload["id"]),
            name=str(payload.get("name") or ""),
            author_name=payload.get("author_name"),
            slug=payload.get("slug"),
            language_name=payload.get("language_name"),
            raw=payload,
        )


@dataclass(frozen=True)
class TafsirAyahEntry:
    entry_id: int
    resource_id: int | None
    verse_id: int | None
    verse_key: str | None
    chapter_id: int | None
    verse_number: int | None
    start_verse_id: int | None
    end_verse_id: int | None
    text: str
    language_name: str | None
    resource_name: str | None
    slug: str | None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "TafsirAyahEntry":
        return cls(
            entry_id=int(payload["id"]),
            resource_id=int(payload["resource_id"]) if payload.get("resource_id") is not None else None,
            verse_id=int(payload["verse_id"]) if payload.get("verse_id") is not None else None,
            verse_key=payload.get("verse_key"),
            chapter_id=int(payload["chapter_id"]) if payload.get("chapter_id") is not None else None,
            verse_number=int(payload["verse_number"]) if payload.get("verse_number") is not None else None,
            start_verse_id=int(payload["start_verse_id"]) if payload.get("start_verse_id") is not None else None,
            end_verse_id=int(payload["end_verse_id"]) if payload.get("end_verse_id") is not None else None,
            text=str(payload.get("text") or ""),
            language_name=payload.get("language_name"),
            resource_name=payload.get("resource_name"),
            slug=payload.get("slug"),
            raw=payload,
        )


@dataclass(frozen=True)
class ApiPagination:
    per_page: int
    current_page: int
    next_page: int | None
    total_pages: int | None = None
    total_records: int | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any] | None) -> "ApiPagination | None":
        if not payload:
            return None
        return cls(
            per_page=int(payload.get("per_page") or 0),
            current_page=int(payload.get("current_page") or 1),
            next_page=(int(payload["next_page"]) if payload.get("next_page") not in {None, ""} else None),
            total_pages=(int(payload["total_pages"]) if payload.get("total_pages") not in {None, ""} else None),
            total_records=(int(payload["total_records"]) if payload.get("total_records") not in {None, ""} else None),
        )
