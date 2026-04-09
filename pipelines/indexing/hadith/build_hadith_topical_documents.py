from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from domains.hadith_topical.enricher import build_enriched_document


def _baab_plus_matn(record: dict) -> str:
    parts = [
        str(record.get('chapter_title_en') or '').strip(),
        str(record.get('english_text') or '').strip(),
    ]
    return ' — '.join(part for part in parts if part)


def build_document_from_record(record: dict) -> dict:
    document = build_enriched_document(
        canonical_ref=str(record['canonical_ref']),
        collection_source_id=str(record['collection_source_id']),
        collection_slug=str(record.get('collection_slug') or ''),
        collection_hadith_number=record.get('collection_hadith_number'),
        book_number=record.get('book_number'),
        chapter_number=record.get('chapter_number'),
        numbering_quality=record.get('numbering_quality'),
        english_text=str(record.get('english_text') or ''),
        arabic_text=record.get('arabic_text'),
        english_narrator=record.get('english_narrator'),
        book_title_en=record.get('book_title_en'),
        chapter_title_en=record.get('chapter_title_en'),
    )

    return {
        'canonical_ref': document.canonical_ref,
        'collection_source_id': document.collection_source_id,
        'collection_slug': document.collection_slug,
        'collection_hadith_number': document.collection_hadith_number,
        'book_number': document.book_number,
        'chapter_number': document.chapter_number,
        'numbering_quality': document.numbering_quality,
        'english_text': document.english_text,
        'arabic_text': document.arabic_text,
        'english_narrator': document.english_narrator,
        'book_title_en': document.book_title_en,
        'chapter_title_en': document.chapter_title_en,
        'baab_plus_matn_en': _baab_plus_matn(record),
        'reference_url': record.get('reference_url'),
        'in_book_reference_text': record.get('in_book_reference_text'),
        'normalized_english_text': document.normalized_english_text,
        'contextual_summary': document.contextual_summary,
        'directive_labels_text': ' '.join(document.directive_labels),
        'topic_tags': list(document.topic_tags),
        'subtopic_tags': list(document.subtopic_tags),
        'directive_labels': list(document.directive_labels),
        'topic_family': document.topic_family,
        'guidance_role': document.guidance_role,
        'central_topic_score': document.central_topic_score,
        'answerability_score': document.answerability_score,
        'narrative_specificity_score': document.narrative_specificity_score,
        'incidental_topic_flags': list(document.incidental_topic_flags),
        'normalized_topic_terms': list(document.normalized_topic_terms),
        'normalized_alias_terms': list(document.normalized_alias_terms),
        'moral_concepts': list(document.moral_concepts),
    }


def build_documents(records: Iterable[dict]) -> list[dict]:
    return [build_document_from_record(record) for record in records]


def write_documents(records: Iterable[dict], output_path: str | Path) -> None:
    path = Path(output_path)
    documents = build_documents(records)

    if path.suffix == '.jsonl':
        path.write_text('\n'.join(json.dumps(document, ensure_ascii=False) for document in documents) + '\n', encoding='utf-8')
        return

    path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding='utf-8')
