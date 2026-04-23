"""Query-time topic resolution — maps user queries to taxonomy leaf slugs.

Deterministic, no LLM. Replaces the old `_CONCEPT_ALIASES` dict in
`infrastructure/search/opensearch/hadith_bukhari_queries.py`. The taxonomy
vocabulary loaded here is the single source of truth for how user queries
find their topical home.

Matching signals per leaf, in order of weight:

    1. Slug token match     (highest — the slug is canonical, e.g. `zina`
                             matches `fiqh.hudood.zina_adultery`)
    2. Vocabulary phrase    (corpus-grounded; matches the actual Bukhari
                             translation phrasing)
    3. Display name token   (curator-chosen words describing the topic)

Phrases that appear in many leafs get a low specificity weight; phrases
unique to one or two leafs score high. Word-boundary matching prevents
substring collisions (no more "zina" matching "Abu Az-Zinad" via the
resolver itself).

Output contract: `TopicResolution` carries the chosen primary topic,
near-ties for secondary boosting, the stripped query tokens, and the
raw score list for observability/debug.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TAXONOMY_PATH = _REPO_ROOT / 'assets' / 'hadith_topical' / 'bukhari_topic_taxonomy.v1.json'


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class TopicResolution:
    """Result of resolving a query against the taxonomy.

    Fields:
        primary_topic      — single slug for the OpenSearch hard filter, or
                             None when confidence is insufficient. When None,
                             the query builder falls back to family-only.
        confident_topics   — slugs that cleared the confidence threshold
                             (includes primary_topic when present). Multiple
                             values indicate a multi-topic query.
        secondary_topics   — slugs below the confidence threshold but above
                             the noise floor. Used for score boosting, NOT
                             filtering.
        normalized_query   — lowercased, stop-phrase stripped query string.
        stripped_tokens    — tokens after fluff removal. Fed to BM25 builder.
        family             — query_family passed in (echoed back for debug).
        scores             — top 5 (slug, score) pairs for observability.
    """
    primary_topic: str | None
    confident_topics: tuple[str, ...]
    secondary_topics: tuple[str, ...]
    normalized_query: str
    stripped_tokens: tuple[str, ...]
    family: str | None
    scores: tuple[tuple[str, float], ...] = field(default_factory=tuple)

    def as_debug(self) -> dict:
        return {
            'primary_topic': self.primary_topic,
            'confident_topics': list(self.confident_topics),
            'secondary_topics': list(self.secondary_topics),
            'normalized_query': self.normalized_query,
            'stripped_tokens': list(self.stripped_tokens),
            'family': self.family,
            'top_scores': [{'slug': s, 'score': round(v, 3)} for s, v in self.scores],
        }


# ---------------------------------------------------------------------------
# Query cleaning
# ---------------------------------------------------------------------------

# Lead-in phrases that add no topical signal.
_STOP_PHRASES: tuple[str, ...] = (
    'what did the prophet say about',
    'what does the prophet say about',
    'what did the prophet pbuh say about',
    'what does islam say about',
    'what does hadith say about',
    'what are the hadiths about',
    'what is the hadith on',
    'what is the ruling on',
    'how did the prophet',
    'how does islam view',
    'what did the messenger say about',
    "what did allah's messenger say about",
    'narrations about',
    'tell me about',
    'hadith on',
    'hadith about',
    'sunnah on',
    'sunnah about',
    'islamic ruling on',
    'ruling on',
    'is it permissible to',
    'is it allowed to',
    'explain',
    'describe',
)

_STOP_WORDS: frozenset[str] = frozenset({
    'what', 'did', 'the', 'prophet', 'say', 'about', 'how', 'does', 'islam',
    'view', 'is', 'it', 'to', 'a', 'an', 'and', 'or', 'of', 'in', 'on',
    'for', 'with', 'that', 'this', 'these', 'those', 'are', 'was', 'were',
    'be', 'been', 'being', 'am', 'do', 'doing', 'have', 'has', 'had',
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall',
    'said', 'says', 'told', 'asked', 'replied', 'narrated',
    'pbuh', 'messenger', 'allah', 'his', 'her', 'their', 'our', 'your', 'my',
    'we', 'they', 'i', 'he', 'she', 'hadith', 'narration',
    'please', 'ruling', 'sunnah', 'any', 'some', 'all', 'more', 'most',
    'no', 'not', 'yes', 'me',
})

_TOKEN_RE = re.compile(r'[a-z]+')


def _strip_query(query: str) -> tuple[str, tuple[str, ...]]:
    """Lowercase, strip lead-in phrases, tokenise, drop stop-words.

    Returns:
        (normalized_query, tokens_tuple)
    """
    q = (query or '').lower()
    for phrase in _STOP_PHRASES:
        q = q.replace(phrase, ' ')
    tokens = tuple(t for t in _TOKEN_RE.findall(q) if t not in _STOP_WORDS and len(t) >= 2)
    return ' '.join(tokens), tokens


# ---------------------------------------------------------------------------
# Taxonomy indexing (cached)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_taxonomy() -> dict:
    return json.loads(_TAXONOMY_PATH.read_text(encoding='utf-8'))


def _slug_tokens(slug: str) -> Iterable[str]:
    """Extract matchable tokens from a slug like `fiqh.hudood.zina_adultery`.

    Stop-word tokens (e.g. the 'what' in `ritual.funerals.death_what_to_say`)
    are filtered because they'd otherwise inherit a huge IDF weight from being
    rare in the slug space while matching common query fluff.
    """
    for part in slug.split('.'):
        for token in part.split('_'):
            if len(token) >= 3 and token.isalpha() and token not in _STOP_WORDS:
                yield token


def _phrase_regex(phrase: str) -> re.Pattern[str]:
    """Word-boundary regex for a phrase; tolerant of varying whitespace."""
    escaped = re.escape(phrase.strip())
    escaped = re.sub(r'\\\ +', r'\\s+', escaped)
    return re.compile(rf'\b{escaped}\b', re.IGNORECASE)


# Weight per signal role.
_ROLE_WEIGHT_VOCAB = 3.0
_ROLE_WEIGHT_SLUG = 3.5      # slug tokens weigh slightly more — they're canonical
_ROLE_WEIGHT_DISPLAY = 1.5


@lru_cache(maxsize=1)
def _build_leaf_index() -> tuple[dict, dict[str, list[tuple[re.Pattern[str], str, float]]]]:
    """Precompute the (pattern, phrase, weight) list for each leaf.

    Weight formula:  role_weight × specificity
      where specificity = total_leafs / cross_leaf_frequency_of_phrase
      (bounded at >=1.0 so no phrase is worthless).
    """
    taxonomy = _load_taxonomy()
    leafs = taxonomy['leaf_topics']
    total_leafs = len(leafs)

    # First pass: tally cross-leaf phrase frequency across all roles combined.
    phrase_freq: dict[str, int] = {}

    def _register(phrase: str) -> None:
        norm = phrase.lower().strip()
        if not norm:
            return
        phrase_freq[norm] = phrase_freq.get(norm, 0) + 1

    leaf_phrases: dict[str, list[tuple[str, str]]] = {}
    for slug, entry in leafs.items():
        phrases: list[tuple[str, str]] = []
        for vocab in (entry.get('vocabulary') or []):
            norm_vocab = vocab.lower().strip()
            if not norm_vocab:
                continue
            _register(norm_vocab)
            phrases.append((norm_vocab, 'vocab'))
            # Also emit individual words from multi-word vocab phrases at a
            # weaker role. Lets "stoning" match the phrase "stoning to death"
            # without losing the phrase-match precedence when the full phrase is present.
            if ' ' in norm_vocab:
                for word in re.findall(r'[a-z]{4,}', norm_vocab):
                    if word in _STOP_WORDS:
                        continue
                    _register(word)
                    phrases.append((word, 'vocab_word'))
        for token in _slug_tokens(slug):
            _register(token)
            phrases.append((token, 'slug'))
        display = (entry.get('display_name') or '').lower()
        for token in re.findall(r'[a-z]{4,}', display):
            if token in _STOP_WORDS:
                continue
            _register(token)
            phrases.append((token, 'display'))
        leaf_phrases[slug] = phrases

    # Second pass: compute weights. When the same phrase appears for a leaf
    # under multiple roles (e.g. both vocab AND slug tokens contain 'ramadan'),
    # keep the HIGHEST-weight role for that phrase rather than the first-seen.
    leaf_patterns: dict[str, list[tuple[re.Pattern[str], str, float]]] = {}
    role_base = {
        'vocab':      _ROLE_WEIGHT_VOCAB,
        'slug':       _ROLE_WEIGHT_SLUG,
        'display':    _ROLE_WEIGHT_DISPLAY,
        'vocab_word': 1.2,  # individual words from multi-word vocab phrases
    }
    for slug, phrases in leaf_phrases.items():
        best_weight: dict[str, float] = {}
        for phrase, role in phrases:
            if not phrase:
                continue
            freq = phrase_freq.get(phrase, 1)
            specificity = max(1.0, total_leafs / max(1, freq))
            weight = role_base.get(role, 1.0) * specificity
            if phrase not in best_weight or best_weight[phrase] < weight:
                best_weight[phrase] = weight

        compiled: list[tuple[re.Pattern[str], str, float]] = []
        for phrase, weight in best_weight.items():
            try:
                pattern = _phrase_regex(phrase)
            except re.error:
                continue
            compiled.append((pattern, phrase, weight))
        leaf_patterns[slug] = compiled

    return leafs, leaf_patterns


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

_DEFAULT_MIN_SCORE = 3.0      # below this: not a confident topic
_DEFAULT_MIN_MARGIN = 2.0     # margin over runner-up for primary assignment
_SECONDARY_SCORE_FLOOR = 1.5  # min score to appear as a secondary


def resolve_topic(
    query: str,
    *,
    query_family: str | None = None,
    min_score: float = _DEFAULT_MIN_SCORE,
    min_margin: float = _DEFAULT_MIN_MARGIN,
) -> TopicResolution:
    """Resolve a user query to the most likely taxonomy leaf.

    When `query_family` is provided, scoring is restricted to leafs in that
    family. Otherwise scoring runs over all 182 leafs and the classifier
    upstream is implicitly trusted to have pre-filtered by source domain.
    """
    normalized, tokens = _strip_query(query)
    leafs, leaf_patterns = _build_leaf_index()

    if query_family:
        candidate_slugs = [s for s, e in leafs.items() if e.get('family') == query_family]
        if not candidate_slugs:  # unknown family → fall back to all leafs
            candidate_slugs = list(leafs.keys())
    else:
        candidate_slugs = list(leafs.keys())

    # Score each candidate against the normalized query AND the raw lowercase query
    # (so multi-word phrases that survive stripping still match).
    scoring_text = f'{normalized} {query.lower()}'

    scores: list[tuple[str, float]] = []
    for slug in candidate_slugs:
        score = 0.0
        for pattern, _phrase, weight in leaf_patterns.get(slug, ()):
            if pattern.search(scoring_text):
                score += weight
        if score > 0:
            scores.append((slug, score))

    # Sort: score desc, then prefer `.general` leafs (they are the natural
    # landing spot when a query is topically broad — e.g. "what is tawhid"
    # lands on tawhid.general over tawhid.shirk when the two tie), then slug alpha.
    def _sort_key(pair: tuple[str, float]) -> tuple:
        slug, score = pair
        is_general = 0 if slug.split('.')[-1] == 'general' else 1
        return (-score, is_general, slug)
    scores.sort(key=_sort_key)

    if not scores:
        return TopicResolution(
            primary_topic=None,
            confident_topics=(),
            secondary_topics=(),
            normalized_query=normalized,
            stripped_tokens=tokens,
            family=query_family,
            scores=(),
        )

    top_slug, top_score = scores[0]
    runner_score = scores[1][1] if len(scores) > 1 else 0.0
    margin = top_score - runner_score

    confident: list[str] = []
    secondary: list[str] = []

    # A `.general` leaf tied with (or ahead of) a sibling specific is still
    # the right primary: the query is broad, the umbrella is the safe landing.
    top_is_general = top_slug.split('.')[-1] == 'general'
    margin_threshold = 0.0 if top_is_general else min_margin

    if top_score >= min_score and margin >= margin_threshold:
        confident.append(top_slug)
        # Near-ties become additional confident topics (for multi-topic queries).
        for slug, score in scores[1:4]:
            if score >= min_score and (top_score - score) <= min_margin:
                confident.append(slug)
            elif score >= _SECONDARY_SCORE_FLOOR:
                secondary.append(slug)
    elif top_score >= min_score:
        # Top score is strong but margin is weak — emit no primary (query is
        # topically ambiguous), expose runners-up as secondary boost targets.
        for slug, score in scores[:4]:
            if score >= _SECONDARY_SCORE_FLOOR:
                secondary.append(slug)
    else:
        # Top score too weak — surface all non-trivial hits as secondary for BM25 boost.
        for slug, score in scores[:4]:
            if score >= _SECONDARY_SCORE_FLOOR:
                secondary.append(slug)

    primary = confident[0] if confident else None
    return TopicResolution(
        primary_topic=primary,
        confident_topics=tuple(confident),
        secondary_topics=tuple(secondary),
        normalized_query=normalized,
        stripped_tokens=tokens,
        family=query_family,
        scores=tuple(scores[:5]),
    )
