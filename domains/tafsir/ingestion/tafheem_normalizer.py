from __future__ import annotations

import json
import re
from pathlib import Path

from domains.tafsir.html_utils import compute_text_hash, normalize_search_text
from domains.tafsir.tafheem_notes import parse_tafheem_raw_text
from domains.tafsir.types import NormalizedTafsirSection

_TAFHEEM_KEY_RE = re.compile(r"^(\d+):(\d+)$")


def load_tafheem_payload(source_file: Path) -> dict[str, dict]:
    payload = json.loads(source_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Tafheem payload must be a SURAH:AYAH keyed object.")
    return payload



def normalize_tafheem_file(
    *,
    source_file: Path,
    source_id: str,
    upstream_provider: str,
    upstream_resource_id: int,
    language_code: str = "en",
) -> dict[int, list[NormalizedTafsirSection]]:
    payload = load_tafheem_payload(source_file)
    section_map: dict[int, list[NormalizedTafsirSection]] = {}

    for verse_key, item in sorted(payload.items(), key=lambda pair: _sort_key(pair[0])):
        if not isinstance(item, dict):
            raise ValueError(f"Entry for {verse_key} must be an object.")

        match = _TAFHEEM_KEY_RE.match(verse_key)
        if not match:
            raise ValueError(f"Invalid Tafheem verse key: {verse_key!r}")

        surah_no = int(match.group(1))
        ayah_no = int(match.group(2))
        raw_text = str(item.get("t") or "").strip()
        if not raw_text:
            continue

        parsed = parse_tafheem_raw_text(raw_text)
        display_text = parsed.display_text
        normalized_text = normalize_search_text(parsed.commentary_text_plain or display_text)
        upstream_entry_id = surah_no * 1000 + ayah_no

        section = NormalizedTafsirSection(
            canonical_section_id=f"{source_id}:{surah_no}:{ayah_no}",
            source_id=source_id,
            upstream_provider=upstream_provider,
            upstream_resource_id=upstream_resource_id,
            upstream_entry_id=upstream_entry_id,
            language_code=language_code,
            slug=f"tafheem-{surah_no}-{ayah_no}",
            language_id=None,
            surah_no=surah_no,
            ayah_start=ayah_no,
            ayah_end=ayah_no,
            anchor_verse_key=verse_key,
            quran_span_ref=verse_key,
            coverage_mode="anchor_only",
            coverage_confidence=0.900,
            text_html=parsed.commentary_text_html,
            text_plain=parsed.commentary_text_plain or display_text,
            text_plain_normalized=normalized_text,
            text_hash=compute_text_hash(normalized_text),
            source_file_path=str(source_file.as_posix()),
            source_manifest_path=None,
            raw_json={
                "verse_key": verse_key,
                "raw_text": raw_text,
                "display_text": display_text,
                "commentary_text_plain": parsed.commentary_text_plain,
                "commentary_text_html": parsed.commentary_text_html,
                "commentary_note_entries": [
                    {"anchor_text": entry.anchor_text, "note_text": entry.note_text}
                    for entry in parsed.note_entries
                ],
                "source_item": item,
                "inline_note_count": parsed.inline_note_count,
            },
        )
        section_map.setdefault(surah_no, []).append(section)

    return section_map



def _sort_key(verse_key: str) -> tuple[int, int]:
    match = _TAFHEEM_KEY_RE.match(verse_key)
    if not match:
        return (10**9, 10**9)
    return (int(match.group(1)), int(match.group(2)))


__all__ = [
    "load_tafheem_payload",
    "normalize_tafheem_file",
]
