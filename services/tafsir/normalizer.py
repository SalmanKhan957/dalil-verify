from __future__ import annotations

import json
import re
from pathlib import Path

from services.tafsir.html_utils import compute_text_hash, normalize_search_text, strip_html_to_text
from services.tafsir.types import NormalizedTafsirSection, RawTafsirRow

_CHAPTER_FILE_RE = re.compile(r"chapter_(\d+)\.json$")


def load_and_validate_chapter_file(path: Path, expected_resource_id: int) -> list[RawTafsirRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    file_chapter_number = _chapter_number_from_filename(path)
    chapter_number = int(payload.get("chapter_number"))
    if file_chapter_number != chapter_number:
        raise ValueError(f"File {path} declares chapter {chapter_number}, expected {file_chapter_number} from filename.")

    tafsirs = payload.get("tafsirs")
    if not isinstance(tafsirs, list):
        raise ValueError(f"File {path} must contain a tafsirs list.")
    if int(payload.get("count", -1)) != len(tafsirs):
        raise ValueError(f"File {path} has count mismatch: payload count {payload.get('count')} vs {len(tafsirs)} rows.")

    rows: list[RawTafsirRow] = []
    seen_verse_keys: set[str] = set()
    for raw in tafsirs:
        for field in ("id", "resource_id", "verse_key", "language_id", "slug", "text"):
            if field not in raw:
                raise ValueError(f"Missing required field {field!r} in {path}.")

        resource_id = int(raw["resource_id"])
        if resource_id != expected_resource_id:
            raise ValueError(f"Resource mismatch in {path}: got {resource_id}, expected {expected_resource_id}.")

        surah_no, ayah_no = _parse_verse_key(str(raw["verse_key"]))
        if surah_no != chapter_number:
            raise ValueError(f"Verse key {raw['verse_key']} does not belong to chapter {chapter_number} in {path}.")
        if raw["verse_key"] in seen_verse_keys:
            raise ValueError(f"Duplicate verse key {raw['verse_key']} in {path}.")
        seen_verse_keys.add(str(raw["verse_key"]))

        text_html = str(raw.get("text") or "")
        text_plain = strip_html_to_text(text_html)
        rows.append(
            RawTafsirRow(
                entry_id=int(raw["id"]),
                resource_id=resource_id,
                surah_no=surah_no,
                ayah_no=ayah_no,
                verse_key=str(raw["verse_key"]),
                language_id=(int(raw["language_id"]) if raw.get("language_id") is not None else None),
                slug=(str(raw["slug"]) if raw.get("slug") is not None else None),
                text_html=text_html,
                text_plain=text_plain,
                text_plain_normalized=normalize_search_text(text_plain),
                raw_json=raw,
            )
        )

    rows.sort(key=lambda row: row.ayah_no)
    _assert_contiguous_ayah_order(rows=rows, chapter_number=chapter_number, path=path)
    return rows


def build_sections_from_rows(
    *,
    rows: list[RawTafsirRow],
    source_id: str,
    upstream_provider: str,
    language_code: str,
    source_file_path: str | None,
    source_manifest_path: str | None,
) -> list[NormalizedTafsirSection]:
    if not rows:
        return []

    sections: list[NormalizedTafsirSection] = []
    idx = 0
    pending_leading_empty_start: int | None = None

    while idx < len(rows):
        row = rows[idx]

        if not row.text_plain_normalized:
            if sections:
                raise ValueError(
                    f"Encountered orphan empty tafsir row at {row.verse_key} after a closed section; corpus shape no longer matches canonicalization rules."
                )

            pending_leading_empty_start = row.ayah_no if pending_leading_empty_start is None else pending_leading_empty_start
            idx += 1
            continue

        ayah_start = pending_leading_empty_start if pending_leading_empty_start is not None else row.ayah_no
        ayah_end = row.ayah_no
        pending_leading_empty_start = None

        next_idx = idx + 1
        while next_idx < len(rows) and not rows[next_idx].text_plain_normalized:
            ayah_end = rows[next_idx].ayah_no
            next_idx += 1

        if ayah_end > ayah_start:
            coverage_mode = "inferred_from_empty_followers"
            coverage_confidence = 0.950
        else:
            coverage_mode = "anchor_only"
            coverage_confidence = 0.850

        quran_span_ref = _render_quran_span_ref(row.surah_no, ayah_start, ayah_end)
        canonical_section_id = f"{source_id}:{row.entry_id}"

        sections.append(
            NormalizedTafsirSection(
                canonical_section_id=canonical_section_id,
                source_id=source_id,
                upstream_provider=upstream_provider,
                upstream_resource_id=row.resource_id,
                upstream_entry_id=row.entry_id,
                language_code=language_code,
                slug=row.slug,
                language_id=row.language_id,
                surah_no=row.surah_no,
                ayah_start=ayah_start,
                ayah_end=ayah_end,
                anchor_verse_key=row.verse_key,
                quran_span_ref=quran_span_ref,
                coverage_mode=coverage_mode,
                coverage_confidence=coverage_confidence,
                text_html=row.text_html,
                text_plain=row.text_plain,
                text_plain_normalized=row.text_plain_normalized,
                text_hash=compute_text_hash(row.text_plain_normalized),
                source_file_path=source_file_path,
                source_manifest_path=source_manifest_path,
                raw_json=row.raw_json,
            )
        )
        idx = next_idx

    if pending_leading_empty_start is not None:
        raise ValueError(
            "Encountered a chapter with only empty tafsir rows; refusing to create an unanchored canonical section."
        )

    return sections


def normalize_resource_directory(
    *,
    source_dir: Path,
    expected_resource_id: int,
    source_id: str,
    upstream_provider: str,
    language_code: str,
) -> dict[int, list[NormalizedTafsirSection]]:
    manifest_path = source_dir / "manifest.json"
    section_map: dict[int, list[NormalizedTafsirSection]] = {}

    chapter_files = sorted(source_dir.glob("chapter_*.json"), key=lambda item: _chapter_number_from_filename(item))
    for chapter_file in chapter_files:
        rows = load_and_validate_chapter_file(chapter_file, expected_resource_id=expected_resource_id)
        section_map[_chapter_number_from_filename(chapter_file)] = build_sections_from_rows(
            rows=rows,
            source_id=source_id,
            upstream_provider=upstream_provider,
            language_code=language_code,
            source_file_path=str(chapter_file.as_posix()),
            source_manifest_path=(str(manifest_path.as_posix()) if manifest_path.exists() else None),
        )
    return section_map


def _parse_verse_key(verse_key: str) -> tuple[int, int]:
    try:
        surah_str, ayah_str = verse_key.split(":", maxsplit=1)
        return int(surah_str), int(ayah_str)
    except ValueError as exc:  # pragma: no cover - defensive path
        raise ValueError(f"Invalid verse key: {verse_key!r}") from exc


def _chapter_number_from_filename(path: Path) -> int:
    match = _CHAPTER_FILE_RE.search(path.name)
    if not match:
        raise ValueError(f"Could not infer chapter number from filename: {path}")
    return int(match.group(1))


def _assert_contiguous_ayah_order(*, rows: list[RawTafsirRow], chapter_number: int, path: Path) -> None:
    expected = 1
    for row in rows:
        if row.surah_no != chapter_number:
            raise ValueError(f"Row {row.verse_key} in {path} does not belong to chapter {chapter_number}.")
        if row.ayah_no != expected:
            raise ValueError(
                f"Chapter {chapter_number} in {path} is not contiguous: expected ayah {expected}, got {row.ayah_no}."
            )
        expected += 1


def _render_quran_span_ref(surah_no: int, ayah_start: int, ayah_end: int) -> str:
    if ayah_start == ayah_end:
        return f"{surah_no}:{ayah_start}"
    return f"{surah_no}:{ayah_start}-{ayah_end}"
