from __future__ import annotations

import json

import pytest

from services.tafsir.normalizer import build_sections_from_rows, load_and_validate_chapter_file


def _write_chapter(tmp_path, chapter_number: int, tafsirs: list[dict]) -> str:
    path = tmp_path / f"chapter_{chapter_number}.json"
    path.write_text(
        json.dumps(
            {
                "resource_id": 169,
                "chapter_number": chapter_number,
                "count": len(tafsirs),
                "tafsirs": tafsirs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(path)


def test_normalizer_builds_multi_ayah_section_from_anchor_plus_empty_followers(tmp_path) -> None:
    chapter_path = _write_chapter(
        tmp_path,
        112,
        [
            {"id": 1, "resource_id": 169, "verse_key": "112:1", "language_id": 38, "text": "<p>Main tafsir</p>", "slug": "ibn"},
            {"id": 2, "resource_id": 169, "verse_key": "112:2", "language_id": 38, "text": "", "slug": "ibn"},
            {"id": 3, "resource_id": 169, "verse_key": "112:3", "language_id": 38, "text": "", "slug": "ibn"},
            {"id": 4, "resource_id": 169, "verse_key": "112:4", "language_id": 38, "text": "", "slug": "ibn"},
        ],
    )

    rows = load_and_validate_chapter_file(tmp_path / "chapter_112.json", expected_resource_id=169)
    sections = build_sections_from_rows(
        rows=rows,
        source_id="tafsir:ibn-kathir-en",
        upstream_provider="quran_foundation",
        language_code="en",
        source_file_path=chapter_path,
        source_manifest_path=None,
    )

    assert len(sections) == 1
    section = sections[0]
    assert section.anchor_verse_key == "112:1"
    assert section.quran_span_ref == "112:1-4"
    assert section.coverage_mode == "inferred_from_empty_followers"


def test_normalizer_builds_anchor_only_section(tmp_path) -> None:
    _write_chapter(
        tmp_path,
        103,
        [
            {"id": 1, "resource_id": 169, "verse_key": "103:1", "language_id": 38, "text": "<p>A</p>", "slug": "ibn"},
            {"id": 2, "resource_id": 169, "verse_key": "103:2", "language_id": 38, "text": "<p>B</p>", "slug": "ibn"},
            {"id": 3, "resource_id": 169, "verse_key": "103:3", "language_id": 38, "text": "<p>C</p>", "slug": "ibn"},
        ],
    )

    rows = load_and_validate_chapter_file(tmp_path / "chapter_103.json", expected_resource_id=169)
    sections = build_sections_from_rows(
        rows=rows,
        source_id="tafsir:ibn-kathir-en",
        upstream_provider="quran_foundation",
        language_code="en",
        source_file_path=None,
        source_manifest_path=None,
    )

    assert [section.quran_span_ref for section in sections] == ["103:1", "103:2", "103:3"]
    assert all(section.coverage_mode == "anchor_only" for section in sections)


def test_normalizer_rejects_duplicate_verse_key(tmp_path) -> None:
    _write_chapter(
        tmp_path,
        1,
        [
            {"id": 1, "resource_id": 169, "verse_key": "1:1", "language_id": 38, "text": "<p>A</p>", "slug": "ibn"},
            {"id": 2, "resource_id": 169, "verse_key": "1:1", "language_id": 38, "text": "<p>B</p>", "slug": "ibn"},
        ],
    )

    with pytest.raises(ValueError, match="Duplicate verse key"):
        load_and_validate_chapter_file(tmp_path / "chapter_1.json", expected_resource_id=169)


def test_normalizer_backfills_leading_empty_rows_into_first_anchor_section(tmp_path) -> None:
    _write_chapter(
        tmp_path,
        105,
        [
            {"id": 1, "resource_id": 169, "verse_key": "105:1", "language_id": 38, "text": "", "slug": "ibn"},
            {"id": 2, "resource_id": 169, "verse_key": "105:2", "language_id": 38, "text": "", "slug": "ibn"},
            {"id": 3, "resource_id": 169, "verse_key": "105:3", "language_id": 38, "text": "", "slug": "ibn"},
            {"id": 4, "resource_id": 169, "verse_key": "105:4", "language_id": 38, "text": "", "slug": "ibn"},
            {"id": 5, "resource_id": 169, "verse_key": "105:5", "language_id": 38, "text": "<p>Elephant story anchor</p>", "slug": "ibn"},
        ],
    )

    rows = load_and_validate_chapter_file(tmp_path / "chapter_105.json", expected_resource_id=169)
    sections = build_sections_from_rows(
        rows=rows,
        source_id="tafsir:ibn-kathir-en",
        upstream_provider="quran_foundation",
        language_code="en",
        source_file_path=None,
        source_manifest_path=None,
    )

    assert len(sections) == 1
    section = sections[0]
    assert section.anchor_verse_key == "105:5"
    assert section.ayah_start == 1
    assert section.ayah_end == 5
    assert section.quran_span_ref == "105:1-5"
    assert section.coverage_mode == "inferred_from_empty_followers"


def test_normalizer_rejects_all_empty_chapter(tmp_path) -> None:
    _write_chapter(
        tmp_path,
        10,
        [
            {"id": 1, "resource_id": 169, "verse_key": "10:1", "language_id": 38, "text": "", "slug": "ibn"},
            {"id": 2, "resource_id": 169, "verse_key": "10:2", "language_id": 38, "text": "", "slug": "ibn"},
        ],
    )

    rows = load_and_validate_chapter_file(tmp_path / "chapter_10.json", expected_resource_id=169)
    with pytest.raises(ValueError, match="only empty tafsir rows"):
        build_sections_from_rows(
            rows=rows,
            source_id="tafsir:ibn-kathir-en",
            upstream_provider="quran_foundation",
            language_code="en",
            source_file_path=None,
            source_manifest_path=None,
        )
