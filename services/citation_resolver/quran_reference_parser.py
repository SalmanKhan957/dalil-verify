# services/citation_resolver/quran_reference_parser.py

from __future__ import annotations

import re
from typing import Any

from services.citation_resolver.surah_aliases import resolve_surah_name

SURAH_AYAH_RANGE_RE = re.compile(r"^(?P<surah>\d{1,3}):(?P<start>\d{1,3})(?:-(?P<end>\d{1,3}))?$")
SURAH_NAME_WITH_OPTIONAL_AYAH_RE = re.compile(
    r"^surah\s+(?P<name>[a-z0-9\-\s]+?)(?:\s+(?:(?:ayah|ayahs|verse|verses)\s*)?(?P<start>\d{1,3})(?:-(?P<end>\d{1,3}))?)?$"
)
AYAH_OF_SURAH_RE = re.compile(
    r"^(?:ayah|ayahs|verse|verses)\s+(?P<start>\d{1,3})(?:-(?P<end>\d{1,3}))?\s+of\s+surah\s+(?P<name>[a-z0-9\-\s]+)$"
)
BARE_SURAH_NAME_RE = re.compile(r"^(?P<name>[a-z0-9\-\s]+)$")


def parse_surah_ayah_range(text: str) -> dict[str, Any] | None:
    match = SURAH_AYAH_RANGE_RE.match(text.strip())
    if not match:
        return None

    surah_no = int(match.group("surah"))
    ayah_start = int(match.group("start"))
    ayah_end = int(match.group("end")) if match.group("end") else ayah_start

    return {
        "surah_no": surah_no,
        "ayah_start": ayah_start,
        "ayah_end": ayah_end,
        "parse_type": "surah_ayah_range",
    }


def parse_surah_name_with_optional_ayah(text: str) -> dict[str, Any] | None:
    match = SURAH_NAME_WITH_OPTIONAL_AYAH_RE.match(text.strip())
    if not match:
        return None

    name = (match.group("name") or "").strip()
    surah_no = resolve_surah_name(name)
    if surah_no is None:
        return None

    start_raw = match.group("start")
    end_raw = match.group("end")
    if start_raw:
        ayah_start = int(start_raw)
        ayah_end = int(end_raw) if end_raw else ayah_start
    else:
        ayah_start = None
        ayah_end = None

    return {
        "surah_no": surah_no,
        "ayah_start": ayah_start,
        "ayah_end": ayah_end,
        "parse_type": "surah_name_with_optional_ayah",
    }


def parse_ayah_of_surah(text: str) -> dict[str, Any] | None:
    match = AYAH_OF_SURAH_RE.match(text.strip())
    if not match:
        return None

    name = (match.group("name") or "").strip()
    surah_no = resolve_surah_name(name)
    if surah_no is None:
        return None

    ayah_start = int(match.group("start"))
    ayah_end = int(match.group("end")) if match.group("end") else ayah_start

    return {
        "surah_no": surah_no,
        "ayah_start": ayah_start,
        "ayah_end": ayah_end,
        "parse_type": "ayah_of_surah_reference",
    }


def parse_bare_surah_name(text: str) -> dict[str, Any] | None:
    match = BARE_SURAH_NAME_RE.match(text.strip())
    if not match:
        return None

    name = (match.group("name") or "").strip()
    surah_no = resolve_surah_name(name)
    if surah_no is None:
        return None

    return {
        "surah_no": surah_no,
        "ayah_start": None,
        "ayah_end": None,
        "parse_type": "bare_surah_name",
    }


def parse_quran_reference(text: str) -> dict[str, Any] | None:
    value = (text or "").strip()
    if not value:
        return None

    for parser in (
        parse_surah_ayah_range,
        parse_surah_name_with_optional_ayah,
        parse_ayah_of_surah,
        parse_bare_surah_name,
    ):
        parsed = parser(value)
        if parsed is not None:
            return parsed

    return None
