from __future__ import annotations

import json
from pathlib import Path

from domains.tafsir.ingestion.tafheem_normalizer import normalize_tafheem_file



def test_normalize_tafheem_file_builds_commentary_aware_sections_and_preserves_raw_notes(tmp_path: Path) -> None:
    source_file = tmp_path / "tafheem.json"
    source_file.write_text(
        json.dumps(
            {
                "2:30": {"t": "Just think[[Footnote one]] when your Lord said to the angels"},
                "2:31": {"t": "And He taught Adam the names[[Footnote two]] all of them"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    section_map = normalize_tafheem_file(
        source_file=source_file,
        source_id="tafsir:tafheem-al-quran-en",
        upstream_provider="external_tafheem_json",
        upstream_resource_id=817001,
        language_code="en",
    )

    assert 2 in section_map
    assert len(section_map[2]) == 2

    first = section_map[2][0]
    assert first.anchor_verse_key == "2:30"
    assert first.quran_span_ref == "2:30"
    assert first.coverage_mode == "anchor_only"
    assert first.text_plain == 'On "Just think": Footnote one'
    assert first.raw_json["raw_text"] == "Just think[[Footnote one]] when your Lord said to the angels"
    assert first.raw_json["display_text"] == 'Just think when your Lord said to the angels'
    assert first.raw_json["inline_note_count"] == 1
    assert first.raw_json["commentary_note_entries"][0]["anchor_text"] == 'Just think'
    assert first.upstream_entry_id == 2030
