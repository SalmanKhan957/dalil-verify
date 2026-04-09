from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from domains.hadith.types import HadithEntryRecord
from domains.query_intelligence.concept_linker import link_query_to_concepts

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+|\n+')
_DIRECT_DIRECTIVE_MARKERS = (
    'do not', 'beware', 'shall not', 'should not', 'must not', 'none of you', 'whoever', 'the best', 'best of',
)
_WARNING_MARKERS = ('beware', 'warning', 'punishment', 'do not', 'forbidden', 'woe')
_VIRTUE_MARKERS = ('best', 'virtue', 'reward', 'superior', 'believer', 'good deed', 'patience is')
_NARRATIVE_MARKERS = (
    'while we were', 'then a man', 'thereupon', 'they asked', 'she asked', 'he asked', 'during', 'journey',
    'campaign', 'battle', 'wives of the prophet', 'noticed anger on his face',
)
_MAX_UNITS_PER_ENTRY = 3
_MIN_UNIT_SCORE = 0.34
_MIN_STRONG_SCORE = 0.46


def _normalize_space(text: str | None) -> str:
    return ' '.join((text or '').split())


def _split_sentences(text: str) -> list[str]:
    normalized = _normalize_space(text)
    if not normalized:
        return []
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
    return parts or [normalized]


def _window_sentences(sentences: list[str], *, max_window_sentences: int = 3) -> list[tuple[int, int, str]]:
    windows: list[tuple[int, int, str]] = []
    for start in range(len(sentences)):
        for width in range(1, max_window_sentences + 1):
            end = start + width
            if end > len(sentences):
                break
            window_text = ' '.join(sentences[start:end]).strip()
            if len(window_text) < 28:
                continue
            windows.append((start, end, window_text))
    return windows or [(0, len(sentences), ' '.join(sentences).strip())]


def _infer_guidance_role(text: str) -> str:
    lowered = text.casefold()
    if any(marker in lowered for marker in _DIRECT_DIRECTIVE_MARKERS):
        return 'direct_moral_instruction'
    if any(marker in lowered for marker in _WARNING_MARKERS):
        return 'warning'
    if any(marker in lowered for marker in _VIRTUE_MARKERS):
        return 'virtue_statement'
    if any(marker in lowered for marker in _NARRATIVE_MARKERS):
        return 'narrative_incident'
    return 'narrative_incident'


def _directness_score(text: str, role: str) -> float:
    lowered = text.casefold()
    base = 0.26 if role == 'narrative_incident' else 0.58
    if 'the prophet' in lowered or "allah's messenger" in lowered:
        base += 0.06
    if role == 'direct_moral_instruction':
        base += 0.16
    elif role == 'warning':
        base += 0.1
    elif role == 'virtue_statement':
        base += 0.08
    if len(text) <= 220:
        base += 0.06
    elif len(text) >= 700:
        base -= 0.14
    elif len(text) >= 420:
        base -= 0.08
    return max(0.0, min(round(base, 3), 1.0))


def _answerability_score(text: str, role: str, concept_count: int, strongest_confidence: float) -> float:
    base = 0.28 + (0.12 * min(concept_count, 2)) + (0.18 * strongest_confidence)
    if role in {'direct_moral_instruction', 'warning', 'virtue_statement'}:
        base += 0.1
    if len(text) <= 240:
        base += 0.06
    elif len(text) >= 500:
        base -= 0.08
    return max(0.0, min(round(base, 3), 1.0))


def _narrative_penalty(text: str, role: str) -> float:
    penalty = 0.14 if role == 'narrative_incident' else 0.03
    lowered = text.casefold()
    if any(marker in lowered for marker in _NARRATIVE_MARKERS):
        penalty += 0.12
    if len(text) >= 360:
        penalty += 0.12
    if len(text) >= 700:
        penalty += 0.12
    return max(0.0, min(round(penalty, 3), 1.0))


def _unit_rank_score(*, strongest_confidence: float, directness: float, answerability: float, narrative_penalty: float, role: str, central_count: int) -> float:
    role_bonus = 0.12 if role in {'direct_moral_instruction', 'warning', 'virtue_statement'} else -0.02
    concept_bonus = min(0.22, 0.12 * max(central_count, 1)) if central_count else 0.0
    score = (
        (0.34 * strongest_confidence)
        + (0.22 * directness)
        + (0.22 * answerability)
        + concept_bonus
        + role_bonus
        - (0.22 * narrative_penalty)
    )
    return max(0.0, min(round(score, 3), 1.0))


def build_guidance_units_for_entry(entry: HadithEntryRecord, *, max_window_sentences: int = 3) -> list[dict]:
    full_text = _normalize_space(entry.english_text)
    sentences = _split_sentences(full_text)
    windows = _window_sentences(sentences, max_window_sentences=max_window_sentences)
    ranked_units: list[tuple[float, int, int, dict]] = []
    for idx, (start, end, window_text) in enumerate(windows, start=1):
        concept_matches = link_query_to_concepts(window_text, domain='hadith', max_results=4, matching_mode='artifact_strict')
        if not concept_matches and len(window_text) > 320:
            continue
        strong_matches = [match for match in concept_matches if match.confidence >= 0.88]
        secondary_matches = [match for match in concept_matches if 0.84 <= match.confidence < 0.88]
        central = tuple(match.slug for match in strong_matches[:2])
        secondary = tuple(match.slug for match in [*strong_matches[2:4], *secondary_matches][:2])
        role = _infer_guidance_role(window_text)
        strongest_confidence = max((float(match.confidence) for match in concept_matches), default=0.0)
        directness = _directness_score(window_text, role)
        answerability = _answerability_score(window_text, role, len(concept_matches), strongest_confidence)
        narrative_penalty = _narrative_penalty(window_text, role)
        builder_rank_score = _unit_rank_score(
            strongest_confidence=strongest_confidence,
            directness=directness,
            answerability=answerability,
            narrative_penalty=narrative_penalty,
            role=role,
            central_count=len(central),
        )
        if builder_rank_score < _MIN_UNIT_SCORE:
            continue
        if not central and role == 'narrative_incident' and builder_rank_score < _MIN_STRONG_SCORE:
            continue
        ranked_units.append(
            (
                builder_rank_score,
                start,
                end,
                {
                    'guidance_unit_id': f"hu:{entry.collection_source_id.replace('hadith:', '')}:{entry.collection_hadith_number}:span:{idx:02d}",
                    'parent_hadith_ref': entry.canonical_ref_collection,
                    'collection_source_id': entry.collection_source_id,
                    'span_text': window_text,
                    'summary_text': window_text[:220].rstrip() + ('…' if len(window_text) > 220 else ''),
                    'guidance_role': role,
                    'topic_family': concept_matches[0].family if concept_matches else None,
                    'central_concept_ids': list(central),
                    'secondary_concept_ids': list(secondary),
                    'directness_score': directness,
                    'answerability_score': answerability,
                    'narrative_penalty': narrative_penalty,
                    'span_start': start,
                    'span_end': end,
                    'numbering_quality': 'collection_number_stable',
                    'metadata': {
                        'english_narrator': entry.english_narrator,
                        'matched_terms': [term for match in concept_matches for term in match.matched_terms],
                        'builder_rank_score': builder_rank_score,
                        'concept_confidence_max': round(strongest_confidence, 3),
                        'concept_match_count': len(concept_matches),
                    },
                },
            )
        )
    ranked_units.sort(key=lambda item: (-item[0], -item[3]['answerability_score'], -item[3]['directness_score'], item[1], item[3]['guidance_unit_id']))
    selected: list[dict] = []
    seen_ranges: set[tuple[int | None, int | None]] = set()
    for _score, _start, _end, unit in ranked_units:
        span_key = (unit.get('span_start'), unit.get('span_end'))
        if span_key in seen_ranges:
            continue
        selected.append(unit)
        seen_ranges.add(span_key)
        if len(selected) >= _MAX_UNITS_PER_ENTRY:
            break
    if selected:
        return selected
    if not full_text:
        return []
    role = _infer_guidance_role(full_text)
    directness = _directness_score(full_text, role)
    answerability = _answerability_score(full_text, role, 0, 0.0)
    narrative_penalty = _narrative_penalty(full_text, role)
    return [
        {
            'guidance_unit_id': f"hu:{entry.collection_source_id.replace('hadith:', '')}:{entry.collection_hadith_number}:span:01",
            'parent_hadith_ref': entry.canonical_ref_collection,
            'collection_source_id': entry.collection_source_id,
            'span_text': full_text,
            'summary_text': full_text[:220].rstrip() + ('…' if len(full_text) > 220 else ''),
            'guidance_role': role,
            'topic_family': None,
            'central_concept_ids': [],
            'secondary_concept_ids': [],
            'directness_score': directness,
            'answerability_score': answerability,
            'narrative_penalty': narrative_penalty,
            'span_start': 0,
            'span_end': len(sentences),
            'numbering_quality': 'collection_number_stable',
            'metadata': {
                'english_narrator': entry.english_narrator,
                'matched_terms': [],
                'builder_rank_score': 0.0,
                'concept_confidence_max': 0.0,
                'concept_match_count': 0,
            },
        }
    ]


def _load_entries(*, database_url: str | None, collection_source_id: str) -> list[HadithEntryRecord]:
    from sqlalchemy import select

    from domains.hadith.repositories.hadith_repository import SqlAlchemyHadithRepository
    from infrastructure.db.models.hadith_entry import HadithEntryORM
    from infrastructure.db.models.source_work import SourceWorkORM
    from infrastructure.db.session import get_session

    with get_session(database_url=database_url) as session:
        repository = SqlAlchemyHadithRepository(session)
        stmt = (
            select(HadithEntryORM.id)
            .join(SourceWorkORM, HadithEntryORM.work_id == SourceWorkORM.id)
            .where(SourceWorkORM.source_id == collection_source_id)
            .order_by(HadithEntryORM.collection_hadith_number.asc())
        )
        entry_ids = [int(row[0]) for row in session.execute(stmt).all()]
        return [repository._get_entry_by_id(entry_id) for entry_id in entry_ids]


def export_guidance_units(*, database_url: str | None, collection_source_id: str, out_file: Path, max_entries: int | None = None) -> dict:
    entries = _load_entries(database_url=database_url, collection_source_id=collection_source_id)
    if max_entries is not None:
        entries = entries[: max(1, int(max_entries))]
    out_file.parent.mkdir(parents=True, exist_ok=True)
    unit_count = 0
    with out_file.open('w', encoding='utf-8') as fh:
        for entry in entries:
            for unit in build_guidance_units_for_entry(entry):
                fh.write(json.dumps(unit, ensure_ascii=False) + '\n')
                unit_count += 1
    return {
        'entries_seen': len(entries),
        'units_written': unit_count,
        'out_file': str(out_file),
        'collection_source_id': collection_source_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Build Hadith guidance-unit JSONL artifact from canonical entries.')
    parser.add_argument('--collection-source-id', required=True)
    parser.add_argument('--out-file', default='data/processed/hadith_topical/guidance_units.v1.jsonl')
    parser.add_argument('--database-url', default=None)
    parser.add_argument('--max-entries', type=int, default=None)
    args = parser.parse_args()
    summary = export_guidance_units(
        database_url=args.database_url,
        collection_source_id=args.collection_source_id,
        out_file=Path(args.out_file),
        max_entries=args.max_entries,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
