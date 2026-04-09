from __future__ import annotations

import re
from typing import Iterable

from domains.hadith_topical.contracts import HadithTopicalDocument
from domains.hadith_topical.taxonomy import ALIAS_TO_TOPIC, TOPIC_BY_SLUG, aliases_for_topic
from shared.utils.lexical import normalize_search_text

_PHRASE_SPLIT_RE = re.compile(r"[.;:!?]\s+")
_DIRECTIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    ('do not ', 'prohibition'),
    ('do not get angry', 'prohibition'),
    ('do not become angry', 'prohibition'),
    ('has ordered', 'command'),
    ('ordered you', 'command'),
    ('best of you', 'virtue'),
    ('the best', 'virtue'),
    ('better than', 'virtue'),
    ('better and more comprehensive', 'virtue'),
    ('beware', 'warning'),
    ('woe', 'warning'),
    ('punishment', 'warning'),
    ('whoever', 'guidance'),
    ('ask whatever you want', 'qa_exchange'),
)
_NARRATIVE_MARKERS = (
    'while we were sitting',
    'then a man came',
    'the wives of the prophet',
    'he said to them',
    'thereupon',
    'so this verse was revealed',
)
_GENERAL_GUIDANCE_MARKERS = (
    'the best',
    'whoever',
    'none is given',
    'real patience',
    'do not get angry',
    'beware',
)


def _combined_search_space(*parts: str | None) -> str:
    return normalize_search_text(' '.join(part for part in parts if part))


def _matched_aliases(search_space: str) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}
    for alias, topic in ALIAS_TO_TOPIC.items():
        if alias in search_space:
            matches.setdefault(topic, []).append(alias)
    return matches


def derive_topic_tags(*, english_text: str, chapter_title_en: str | None = None, book_title_en: str | None = None) -> tuple[str, ...]:
    search_space = _combined_search_space(english_text, chapter_title_en, book_title_en)
    matches = _matched_aliases(search_space)
    ranked = sorted(matches.items(), key=lambda item: (-len(item[1]), item[0]))
    return tuple(topic for topic, _aliases in ranked)


def derive_directive_labels(*, english_text: str, chapter_title_en: str | None = None) -> tuple[str, ...]:
    search_space = _combined_search_space(english_text, chapter_title_en)
    labels: list[str] = []
    seen: set[str] = set()
    for needle, label in _DIRECTIVE_PATTERNS:
        if needle in search_space and label not in seen:
            labels.append(label)
            seen.add(label)
    if ' said ' in f' {search_space} ' and 'qa_exchange' not in seen:
        labels.append('story')
    return tuple(labels)


def build_contextual_summary(
    *,
    english_text: str,
    chapter_title_en: str | None = None,
    book_title_en: str | None = None,
    english_narrator: str | None = None,
    topic_tags: Iterable[str] = (),
    directive_labels: Iterable[str] = (),
    max_length: int = 420,
) -> str:
    text = ' '.join(part.strip() for part in (book_title_en, chapter_title_en, english_narrator, english_text) if part and part.strip())
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ''
    first_sentence = _PHRASE_SPLIT_RE.split(text, maxsplit=1)[0].strip()
    summary = first_sentence or text[:max_length]
    prefixes: list[str] = []
    if topic_tags:
        prefixes.append(f"topics={', '.join(topic_tags)}")
    if directive_labels:
        prefixes.append(f"labels={', '.join(directive_labels)}")
    if prefixes:
        summary = f"[{' ; '.join(prefixes)}] {summary}".replace(' ; ', '; ')
    return summary[:max_length]


def derive_guidance_role(*, directive_labels: tuple[str, ...], english_text: str, chapter_title_en: str | None = None) -> str:
    search_space = _combined_search_space(english_text, chapter_title_en)
    if ('qa_exchange' in directive_labels or 'questions' in normalize_search_text(chapter_title_en or '')) and any(marker in search_space for marker in ('prayer', 'zakat', 'fasts', 'ask whatever you want', 'questions to the prophet')):
        return 'narrative_incident'
    if 'warning' in directive_labels or 'prohibition' in directive_labels:
        if any(marker in search_space for marker in ('beware', 'woe', 'do not get angry', 'do not become angry')):
            return 'direct_moral_instruction'
        return 'warning'
    if 'virtue' in directive_labels:
        return 'virtue_statement'
    if 'command' in directive_labels:
        return 'legal_specific_case'
    if 'qa_exchange' in directive_labels or any(marker in search_space for marker in _NARRATIVE_MARKERS):
        return 'narrative_incident'
    return 'narrative_incident'


def derive_narrative_specificity_score(*, english_text: str, chapter_title_en: str | None = None, guidance_role: str) -> float:
    search_space = _combined_search_space(english_text, chapter_title_en)
    token_count = len(search_space.split())
    score = 0.2 if guidance_role in {'direct_moral_instruction', 'virtue_statement'} else 0.45
    if any(marker in search_space for marker in _NARRATIVE_MARKERS):
        score += 0.2
    if token_count >= 80:
        score += 0.15
    if 'so this verse was revealed' in search_space:
        score += 0.1
    return round(max(0.0, min(score, 1.0)), 3)


def derive_central_topic_score(
    *,
    topic_tags: tuple[str, ...],
    matched_aliases: dict[str, list[str]],
    chapter_title_en: str | None = None,
    book_title_en: str | None = None,
    english_text: str,
    guidance_role: str,
) -> float:
    if not topic_tags:
        return 0.0
    primary = topic_tags[0]
    aliases = matched_aliases.get(primary, [])
    title_space = _combined_search_space(chapter_title_en, book_title_en)
    body_space = normalize_search_text(english_text)
    title_hit = any(alias in title_space for alias in aliases_for_topic(primary))
    body_hits = sum(body_space.count(alias) for alias in aliases)
    score = 0.18
    if title_hit:
        score += 0.35
    if body_hits >= 2:
        score += 0.25
    elif body_hits == 1:
        score += 0.1
    if guidance_role in {'direct_moral_instruction', 'virtue_statement'}:
        score += 0.18
    if any(marker in body_space for marker in _GENERAL_GUIDANCE_MARKERS):
        score += 0.08
    if len(body_space.split()) <= 60 and body_hits:
        score += 0.05
    if guidance_role == 'narrative_incident' and not title_hit:
        score -= 0.18
    return round(max(0.0, min(score, 1.0)), 3)


def derive_incidental_topic_flags(
    *,
    topic_tags: tuple[str, ...],
    matched_aliases: dict[str, list[str]],
    chapter_title_en: str | None = None,
    book_title_en: str | None = None,
    english_text: str,
    guidance_role: str,
) -> tuple[str, ...]:
    if not topic_tags:
        return ()
    primary = topic_tags[0]
    title_space = _combined_search_space(chapter_title_en, book_title_en)
    body_space = normalize_search_text(english_text)
    body_token_count = len(body_space.split())
    body_hits = sum(body_space.count(alias) for alias in matched_aliases.get(primary, []))
    title_has_topic = any(alias in title_space for alias in aliases_for_topic(primary))
    flags: list[str] = []
    if body_hits <= 1 and not title_has_topic and body_token_count >= 70:
        flags.append('incidental_mention_risk')
    if guidance_role == 'narrative_incident' and not title_has_topic:
        flags.append('narrative_specific_risk')
    if primary == 'anger':
        if 'do not get angry' not in body_space:
            if body_hits <= 2:
                flags.append('anger_phrase_not_central')
            if 'noticed anger on his face' in body_space or 'anger on his face' in body_space:
                flags.append('incidental_mention_risk')
        if ('questions' in normalize_search_text(chapter_title_en or '') and any(marker in body_space for marker in ('prayer', 'zakat', 'fasts'))):
            flags.append('incidental_mention_risk')
    if primary == 'hasad' and 'wives of the prophet' in body_space:
        flags.append('jealousy_context_specific')
    if primary == 'rizq' and 'provision' in body_space and 'journey' in body_space:
        flags.append('travel_provision_context')
    return tuple(dict.fromkeys(flags))


def derive_answerability_score(*, central_topic_score: float, narrative_specificity_score: float, guidance_role: str, incidental_flags: tuple[str, ...]) -> float:
    score = central_topic_score
    if guidance_role in {'direct_moral_instruction', 'virtue_statement', 'warning'}:
        score += 0.1
    if 'incidental_mention_risk' in incidental_flags:
        score -= 0.18
    if 'narrative_specific_risk' in incidental_flags:
        score -= 0.12
    score -= narrative_specificity_score * 0.12
    return round(max(0.0, min(score, 1.0)), 3)


def derive_moral_concepts(*, topic_tags: tuple[str, ...], directive_labels: tuple[str, ...]) -> tuple[str, ...]:
    concepts = list(topic_tags)
    concepts.extend(label for label in directive_labels if label in {'warning', 'virtue', 'guidance', 'prohibition', 'command'})
    return tuple(dict.fromkeys(concepts))


def build_enriched_document(
    *,
    canonical_ref: str,
    collection_source_id: str,
    collection_slug: str,
    collection_hadith_number: int | None,
    book_number: int | None,
    chapter_number: int | None,
    numbering_quality: str | None,
    english_text: str,
    arabic_text: str | None = None,
    english_narrator: str | None = None,
    book_title_en: str | None = None,
    chapter_title_en: str | None = None,
) -> HadithTopicalDocument:
    search_space = _combined_search_space(english_text, chapter_title_en, book_title_en)
    matched_aliases = _matched_aliases(search_space)
    topic_tags = derive_topic_tags(english_text=english_text, chapter_title_en=chapter_title_en, book_title_en=book_title_en)
    directive_labels = derive_directive_labels(english_text=english_text, chapter_title_en=chapter_title_en)
    contextual_summary = build_contextual_summary(
        english_text=english_text,
        chapter_title_en=chapter_title_en,
        book_title_en=book_title_en,
        english_narrator=english_narrator,
        topic_tags=topic_tags,
        directive_labels=directive_labels,
    )
    normalized_topic_terms = tuple(dict.fromkeys(topic_tags))
    normalized_alias_terms = tuple(dict.fromkeys(alias for topic in topic_tags for alias in matched_aliases.get(topic, [])))
    topic_family = TOPIC_BY_SLUG.get(topic_tags[0]).family if topic_tags else None
    guidance_role = derive_guidance_role(directive_labels=directive_labels, english_text=english_text, chapter_title_en=chapter_title_en)
    central_topic_score = derive_central_topic_score(
        topic_tags=topic_tags,
        matched_aliases=matched_aliases,
        chapter_title_en=chapter_title_en,
        book_title_en=book_title_en,
        english_text=english_text,
        guidance_role=guidance_role,
    )
    narrative_specificity_score = derive_narrative_specificity_score(
        english_text=english_text,
        chapter_title_en=chapter_title_en,
        guidance_role=guidance_role,
    )
    incidental_topic_flags = derive_incidental_topic_flags(
        topic_tags=topic_tags,
        matched_aliases=matched_aliases,
        chapter_title_en=chapter_title_en,
        book_title_en=book_title_en,
        english_text=english_text,
        guidance_role=guidance_role,
    )
    answerability_score = derive_answerability_score(
        central_topic_score=central_topic_score,
        narrative_specificity_score=narrative_specificity_score,
        guidance_role=guidance_role,
        incidental_flags=incidental_topic_flags,
    )
    subtopic_tags: list[str] = []
    if 'qa_exchange' in directive_labels:
        subtopic_tags.append('question_answer_exchange')
    if 'travel provision' in search_space or ('journey' in search_space and 'provision' in search_space):
        subtopic_tags.append('travel_provision')
    if 'do not get angry' in search_space:
        subtopic_tags.append('anger_control')
    moral_concepts = derive_moral_concepts(topic_tags=topic_tags, directive_labels=directive_labels)
    return HadithTopicalDocument(
        canonical_ref=canonical_ref,
        collection_source_id=collection_source_id,
        collection_slug=collection_slug,
        collection_hadith_number=collection_hadith_number,
        book_number=book_number,
        chapter_number=chapter_number,
        numbering_quality=numbering_quality,
        english_text=english_text,
        arabic_text=arabic_text,
        english_narrator=english_narrator,
        book_title_en=book_title_en,
        chapter_title_en=chapter_title_en,
        normalized_english_text=normalize_search_text(english_text),
        contextual_summary=contextual_summary,
        topic_tags=topic_tags,
        subtopic_tags=tuple(dict.fromkeys(subtopic_tags)),
        directive_labels=directive_labels,
        topic_family=topic_family,
        guidance_role=guidance_role,
        central_topic_score=central_topic_score,
        answerability_score=answerability_score,
        narrative_specificity_score=narrative_specificity_score,
        incidental_topic_flags=incidental_topic_flags,
        normalized_topic_terms=normalized_topic_terms,
        normalized_alias_terms=normalized_alias_terms,
        moral_concepts=moral_concepts,
    )
