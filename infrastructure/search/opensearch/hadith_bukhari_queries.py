"""OpenSearch query builders for the Bukhari topical hybrid index.

This module is exclusively responsible for constructing well-formed OpenSearch
query bodies against `hadith_topical_bukhari`.  It does not execute queries,
combine results, or map hits — all of that belongs in candidate_generation.py.

Index fields used:
    synthetic_baab_label  — text, english analyzer, primary BM25 boost target
    matn_text             — text, english analyzer, secondary BM25 field
    query_family          — keyword, pre-filter (scopes candidate pool)
    is_stub               — boolean, mandatory exclusion filter
    has_direct_prophetic_statement — boolean, score-time boost in candidate_generation
    matn_embedding        — knn_vector(1536), dense retrieval target

Narrator field exclusion:
    The `narrator` field is intentionally absent from ALL match clauses.
    Narrator names can contain substrings of query terms (e.g. "Abu Az-Zinad"
    contains "zinad"). Searching this field produces false positives that the
    evidence gate cannot reliably filter.

The vocabulary mismatch problem — THE ROOT CAUSE of the zina/riba failures:
    Bukhari's English translation uses formal 1970s equivalents for Arabic terms.
    "Zina"  is never used — the text says "illegal sexual intercourse".
    "Riba"  is never used — the text says "usury".
    "Khamr" is never used — the text says "wine" or "alcoholic drink".

    A BM25 query using the Arabic term or modern English synonym returns zero
    relevant hits against matn_text.  The AND operator then correctly returns
    nothing (concept genuinely absent), while the OR operator incorrectly returns
    narrator-name substring matches like "Abu Az-Zinad" for "zina".

    The _CONCEPT_ALIASES map is the permanent fix.  Before any OpenSearch query
    is built, Arabic/modern-English terms are expanded to the corpus-specific
    translation vocabulary.  "Zina" becomes "illegal sexual intercourse adultery
    rajam stoning" — all of which exist in Book 86 matn_text.

BM25 scoring layers:
    1. Verbatim phrase match on synthetic_baab_label (boost 10.0)
    2. Strict cross-fields AND on [synthetic_baab_label^5, matn_text^1] (boost 2.0)
    3. Per-alias individual boost clauses on both fields (boost 1.8 / 1.2)
"""
from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Family normalisation
# ---------------------------------------------------------------------------

_DALIL_FAMILY_TO_BUKHARI: dict[str, str] = {
    'akhlaq':           'akhlaq',
    'adab':             'akhlaq',
    'moral_guidance':   'akhlaq',
    'character':        'akhlaq',
    'virtue':           'akhlaq',
    'ritual':           'ritual',
    'ritual_practice':  'ritual',
    'ibadah':           'ritual',
    'salah':            'ritual',
    'sawm':             'ritual',
    'zakat':            'ritual',
    'hajj':             'ritual',
    'fiqh':             'fiqh',
    'halal_haram':      'fiqh',
    'legal':            'fiqh',
    'marriage_divorce': 'fiqh',
    'zina':             'fiqh',
    'hudood':           'fiqh',
    'punishment':       'fiqh',
    'hadd':             'fiqh',
    'riba':             'fiqh',
    'trade':            'fiqh',
    'contract':         'fiqh',
    'inheritance':      'fiqh',
    'historical':       'historical',
    'seerah':           'historical',
    'narrative_event':  'historical',
    'eschatology':      'eschatology',
    'entity_eschatology': 'eschatology',
    'fitan':            'eschatology',
    'end_times':        'eschatology',
    'judgement':        'eschatology',
    'resurrection':     'eschatology',
    'akhirah':          'eschatology',
    'aqeedah':          'aqeedah',
    'belief':           'aqeedah',
    'tawhid':           'aqeedah',
    'quran':            'quran',
    'tafsir':           'quran',
    'foundational':     'foundational',
    'usul':             'foundational',
}


def normalise_family(dalil_family: str | None) -> str | None:
    if not dalil_family:
        return None
    return _DALIL_FAMILY_TO_BUKHARI.get(str(dalil_family).strip().lower())


# ---------------------------------------------------------------------------
# Concept alias / vocabulary bridge
# ---------------------------------------------------------------------------

_CONCEPT_ALIASES: dict[str, list[str]] = {
    # Hudood / prohibited acts
    'zina':             ['illegal sexual intercourse', 'adultery', 'rajam',
                         'stoning to death', 'fornication'],
    'rajm':             ['stoning', 'stoned to death', 'stoning to death', 'rajam'],
    'riba':             ['usury', 'interest', 'unlawful gain', 'riba'],
    'khamr':            ['wine', 'alcoholic drink', 'intoxicant', 'nabidh'],
    'qazf':             ['slander', 'false accusation', 'accuse of illegal intercourse'],
    'sariqa':           ['theft', 'stealing', 'thief', 'cut off the hand', 'cutting the hand'],
    'qisas':            ['retaliation', 'blood money', 'retribution'],
    'riddah':           ['apostasy', 'apostate', 'renegade', 'who changes his religion'],
    # Akhlaq
    'ghayba':           ['backbiting', 'speaking ill', 'tale-bearer'],
    'kibr':             ['arrogance', 'pride', 'haughty', 'boasting'],
    'hasad':            ['envy', 'jealousy', 'envious', 'jealous'],
    'ghadab':           ['anger', 'angry', 'temper', 'rage', 'do not become angry'],
    'kadhib':           ['lying', 'false statements', 'dishonesty', 'liar', 'falsehood'],
    'haya':             ['modesty', 'shyness', 'bashful'],
    'sabr':             ['patience', 'patient', 'endurance', 'perseverance'],
    'shukr':            ['gratitude', 'thankfulness', 'grateful', 'thankful'],
    'tawbah':           ['repentance', 'repent', 'seek forgiveness', 'istighfar'],
    'nifaq':            ['hypocrisy', 'hypocrite', 'sign of a hypocrite'],
    'tawadu':           ['humility', 'humble', 'modesty'],
    # Aqeedah
    'tawhid':           ['oneness of allah', 'monotheism', 'associating partners'],
    'shirk':            ['associating partners', 'polytheism', 'idol worship'],
    'tawakkul':         ['reliance on allah', 'trust in allah'],
    'qadar':            ['divine will', 'predestination', 'decree of allah'],
    # Ritual
    'sawm':             ['fasting', 'fast', 'ramadan'],
    'zakat_term':       ['obligatory charity', 'poor-due', 'almsgiving', 'zakah'],
    'wudu':             ['ablution', 'purification', 'wash before prayer'],
    'ghusl':            ['ritual bath', 'major purification'],
    # Fiqh
    'nikah':            ['marriage', 'nikah', 'mahr', 'dowry'],
    'talaq':            ['divorce', 'repudiation', 'pronounce divorce'],
    'miras':            ['inheritance', 'estate', 'heir', 'bequeath'],
    # Eschatology
    'dajjal':           ['dajjal', 'false messiah', 'antichrist', 'one-eyed'],
    'mahdi':            ['mahdi', 'guided one', 'fills the earth with justice'],
    'yawm_qiyama':      ['day of resurrection', 'day of judgment', 'the hour'],
    'jannah':           ['paradise', 'garden', 'rivers of paradise'],
    'jahannam':         ['hellfire', 'hell', 'fire of hell'],
    'fitan':            ['trials', 'afflictions', 'civil strife', 'tribulations'],
}

_STOP_PHRASES: list[str] = [
    'what did the prophet say about',
    'what does the prophet say about',
    'what did the prophet pbuh say about',
    'what does islam say about',
    'what does hadith say about',
    'what are the hadiths about',
    'narrations about',
    'tell me about',
    'what is the hadith on',
    'hadith on',
    'hadith about',
    'sunnah on',
    'sunnah about',
    'what is the ruling on',
    'ruling on',
    'how does islam view',
    'islamic ruling on',
    'is it permissible to',
    'is it allowed to',
    'what did the messenger say about',
    "what did allah's messenger say about",
]

_STOP_WORDS: frozenset[str] = frozenset({
    'what', 'did', 'the', 'prophet', 'say', 'about', 'how', 'does', 'islam',
    'view', 'is', 'it', 'to', 'a', 'an', 'and', 'or', 'of', 'in', 'on',
    'for', 'with', 'that', 'this', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'pbuh', 'messenger', 'allah',
    'his', 'her', 'their', 'our', 'your', 'my', 'we', 'they', 'i', 'he',
    'she', 'hadith', 'narration', 'tell', 'me', 'regarding', 'concerning',
    'related', 'sunnah', 'ruling', 'please', 'can', 'could', 'would',
    'should', 'may', 'might', 'said', 'says', 'mentioned', 'narrated',
})


def _strip_fluff(query: str) -> str:
    q = query.lower().strip()
    for phrase in _STOP_PHRASES:
        q = q.replace(phrase, ' ')
    tokens = [t for t in re.split(r'\W+', q) if t and t not in _STOP_WORDS and len(t) > 1]
    return ' '.join(tokens)


def _expand_concepts(core_query: str) -> tuple[str, list[str]]:
    """Expand Islamic terms to corpus translation vocabulary using word-boundary matching.

    Returns:
        (primary_search_term, [individual_alias_terms])
    """
    q_lower = core_query.lower().strip()
    all_expansions: list[str] = []

    for concept, aliases in _CONCEPT_ALIASES.items():
        concept_key = concept.replace('_term', '')  # handle duplicate keys like zakat_term
        if re.search(r'\b' + re.escape(concept_key) + r'\b', q_lower):
            all_expansions.extend(aliases)

    if all_expansions:
        seen: set[str] = set()
        unique: list[str] = []
        for a in all_expansions:
            if a not in seen:
                seen.add(a)
                unique.append(a)
        return ' '.join(unique[:4]), unique[:6]

    return q_lower, [q_lower] if q_lower else []


def prepare_search_terms(
    normalized_query: str,
    topic_candidates: tuple[str, ...] = (),
) -> tuple[str, list[str]]:
    """Strip conversational fluff, expand concepts, supplement with topic candidates.

    Returns:
        (primary_search_term, [individual_topic_terms_for_boost_clauses])
    """
    core = _strip_fluff(normalized_query)
    expanded_term, alias_list = _expand_concepts(core)

    extra_topics: list[str] = []
    for topic in topic_candidates:
        topic_core = _strip_fluff(topic)
        _, topic_aliases = _expand_concepts(topic_core)
        for a in (topic_aliases if topic_aliases else ([topic_core] if topic_core else [])):
            if a not in alias_list and a not in extra_topics:
                extra_topics.append(a)

    all_topics = alias_list + extra_topics

    if not expanded_term and not all_topics:
        expanded_term = normalized_query
        all_topics = [normalized_query]

    return expanded_term, all_topics


# ---------------------------------------------------------------------------
# BM25 query
# ---------------------------------------------------------------------------

def build_bukhari_bm25_query(
    *,
    normalized_query: str,
    topic_candidates: tuple[str, ...] = (),
    dalil_family: str | None = None,
    size: int = 20,
) -> dict[str, Any]:
    """Build a precision-weighted BM25 query against hadith_topical_bukhari."""
    bukhari_family = normalise_family(dalil_family)

    must_filters: list[dict[str, Any]] = [{'term': {'is_stub': False}}]
    if bukhari_family:
        must_filters.append({'term': {'query_family': bukhari_family}})

    primary_term, all_topic_terms = prepare_search_terms(normalized_query, topic_candidates)

    should: list[dict[str, Any]] = []

    # We treat each expanded concept/alias as a strict phrase or AND match
    for term in all_topic_terms:
        if not term:
            continue
            
        # Phrase match heavily boosted
        should.append({
            'match_phrase': {
                'synthetic_baab_label': {'query': term, 'boost': 10.0}
            }
        })
        should.append({
            'match_phrase': {
                'matn_text': {'query': term, 'boost': 3.0}
            }
        })
        # Strict cross-fields AND for multi-word aliases (e.g. "illegal sexual intercourse")
        should.append({
            'multi_match': {
                'query': term,
                'fields': ['synthetic_baab_label^5', 'matn_text^1'],
                'type': 'cross_fields',
                'operator': 'and',
                'boost': 2.0
            }
        })

    return {
        'size': max(1, int(size)),
        'query': {
            'bool': {
                'filter': must_filters,
                'should': should or [{'match_all': {}}],
                'minimum_should_match': 1,
            },
        },
        '_source': {
            'excludes': ['matn_embedding'],
        },
    }


# ---------------------------------------------------------------------------
# kNN query
# ---------------------------------------------------------------------------

def build_bukhari_knn_query(
    *,
    query_vector: list[float],
    dalil_family: str | None = None,
    k: int = 20,
) -> dict[str, Any]:
    """Build a kNN query against the matn_embedding field."""
    bukhari_family = normalise_family(dalil_family)

    knn_filter_clauses: list[dict[str, Any]] = [
        {'term': {'is_stub': False}},
    ]
    if bukhari_family:
        knn_filter_clauses.append({'term': {'query_family': bukhari_family}})

    knn_field: dict[str, Any] = {
        'vector': query_vector,
        'k':      max(1, int(k)),
    }
    if knn_filter_clauses:
        knn_field['filter'] = {
            'bool': {'must': knn_filter_clauses},
        }

    return {
        'size': max(1, int(k)),
        'query': {
            'knn': {
                'matn_embedding': knn_field,
            },
        },
        '_source': {
            'excludes': ['matn_embedding'],
        },
    }
