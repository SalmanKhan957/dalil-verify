"""Rule-based topical enrichment for Bukhari — zero-cost fallback for enrich_hadiths.py.

Produces the same output schema as the LLM enricher, writing to the same sibling
file `data/raw/hadith/meeatif/bukhari_enriched_v3_topical.json`. Resume-safe: by
default it only processes records NOT already present in the output file, so it
composes cleanly with an interrupted LLM run.

Assignment strategy — three layers, highest confidence first:

    Layer 1  Baab-level exact match
             When the record's `synthetic_baab_label` matches a leaf topic's
             `source_baabs` entry exactly, assign that leaf with density=0.92.
             Highest confidence — the baab was named for that topic.

    Layer 2  Kitab-level unique mapping
             If the record's `kitab_title_english` appears in exactly one
             leaf topic's `source_kitabs` list, assign that leaf with
             density=0.85. High confidence — the kitab is monothematic.

    Layer 3  Vocabulary scoring against cleaned matn
             For everything else, compute a score per candidate leaf within
             the same `query_family`:
                 score = family_weight
                       + phrase_match_bonus (any vocab phrase found with \\b word boundaries)
                       + kitab_signal       (+0.15 if kitab appears in the leaf's source_kitabs)
                       + baab_signal        (+0.10 if baab appears as a substring in source_baabs)
             Assign the top-scoring leaf if margin over runner-up >= 0.15 and
             absolute score >= 0.55. Otherwise abstain.

All vocabulary matching is word-boundary-safe — the rule-based path does not
reproduce the lazy `in` substring bug that caused the zina/Zinad collision.

Usage:
    python -m pipelines.hadith_topical.enrichment.enrich_rulebased
    python -m pipelines.hadith_topical.enrichment.enrich_rulebased --force
    python -m pipelines.hadith_topical.enrichment.enrich_rulebased --limit 50 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from pipelines.hadith_topical.enrichment.enrich_hadiths import (
    _OUT_JSON,
    _REPO_ROOT,
    _SOURCE_JSON,
    _TAXONOMY_JSON,
    _REPORT_MD,
    clean_matn,
    load_existing,
    load_taxonomy,
    write_report,
    atomic_write,
)

log = logging.getLogger('enrich_rulebased')

_ENRICHMENT_VERSION = 'v1-rulebased'
_ENRICHMENT_MODEL = 'rulebased:taxonomy_v1'

# Scoring thresholds
_MIN_SCORE = 0.55
_MIN_MARGIN = 0.15
_DENSITY_BAAB_MATCH = 0.92
_DENSITY_KITAB_UNIQUE = 0.85
_DENSITY_VOCAB_STRONG = 0.75
_DENSITY_VOCAB_MODERATE = 0.60


# ---------------------------------------------------------------------------
# Taxonomy indexing — precompute matching aids once
# ---------------------------------------------------------------------------

def _build_phrase_regex(phrase: str) -> re.Pattern[str]:
    """Return a case-insensitive word-boundary regex for a phrase.

    Multi-word phrases still use \\b at the external ends only, so
    "illegal sexual intercourse" matches within a matn but doesn't
    falsely match a substring inside a longer token.
    """
    escaped = re.escape(phrase.strip())
    # Allow flexible whitespace between words
    escaped = re.sub(r'\\\ +', r'\\s+', escaped)
    return re.compile(rf'\b{escaped}\b', re.IGNORECASE)


def index_taxonomy(taxonomy: dict[str, Any]) -> dict[str, Any]:
    """Precompute matching structures from the taxonomy for fast lookup."""
    leafs = taxonomy['leaf_topics']

    baab_to_slug: dict[str, str] = {}
    kitab_to_slugs: dict[str, list[str]] = defaultdict(list)
    family_to_slugs: dict[str, list[str]] = defaultdict(list)
    leaf_regexes: dict[str, list[re.Pattern[str]]] = {}

    for slug, entry in leafs.items():
        family = entry['family']
        family_to_slugs[family].append(slug)

        for baab in entry.get('source_baabs') or []:
            # Exact baab can only map to one leaf; last-writer-wins is fine
            # because the taxonomy was authored to avoid baab collisions.
            baab_to_slug[baab] = slug

        for kitab in entry.get('source_kitabs') or []:
            kitab_to_slugs[kitab].append(slug)

        regexes = []
        for phrase in entry.get('vocabulary') or []:
            try:
                regexes.append(_build_phrase_regex(phrase))
            except re.error as exc:  # pragma: no cover
                log.warning('Bad phrase %r in %s: %s', phrase, slug, exc)
        leaf_regexes[slug] = regexes

    return {
        'leafs': leafs,
        'baab_to_slug': baab_to_slug,
        'kitab_to_slugs': dict(kitab_to_slugs),
        'family_to_slugs': dict(family_to_slugs),
        'leaf_regexes': leaf_regexes,
    }


# ---------------------------------------------------------------------------
# Per-record rule application
# ---------------------------------------------------------------------------

def _matched_phrases(matn_clean: str, regexes: list[re.Pattern[str]], leaf_vocab: list[str]) -> list[str]:
    found: list[str] = []
    for pattern, phrase in zip(regexes, leaf_vocab):
        if pattern.search(matn_clean):
            found.append(phrase.lower().strip())
    # Preserve order, dedupe
    seen: set[str] = set()
    unique: list[str] = []
    for phrase in found:
        if phrase not in seen:
            seen.add(phrase)
            unique.append(phrase)
    return unique[:6]


def score_candidate_leaf(
    slug: str,
    taxonomy_index: dict[str, Any],
    record: dict[str, Any],
    matn_clean: str,
    matn_tokens: set[str],
) -> tuple[float, list[str]]:
    """Score a candidate leaf for a record. Returns (score, matched_phrases)."""
    leaf = taxonomy_index['leafs'][slug]
    vocab = leaf.get('vocabulary') or []
    regexes = taxonomy_index['leaf_regexes'].get(slug, [])

    matched_phrases = _matched_phrases(matn_clean, regexes, vocab)

    # Base family weight — we only score leaves within the matching family,
    # so this is a constant floor.
    score = 0.30

    # Phrase match bonus — first match is worth most
    if matched_phrases:
        score += 0.35
        if len(matched_phrases) >= 2:
            score += 0.12
        if len(matched_phrases) >= 3:
            score += 0.08

    # Kitab signal
    kitab = record.get('kitab_title_english') or ''
    if kitab and kitab in (leaf.get('source_kitabs') or []):
        score += 0.15

    # Baab signal — soft substring match on source_baabs, since the taxonomy
    # authored baabs were compact phrases that may appear inside longer synthetic labels.
    baab = record.get('synthetic_baab_label') or ''
    if baab:
        for src_baab in (leaf.get('source_baabs') or []):
            if src_baab.lower() in baab.lower() or baab.lower() in src_baab.lower():
                score += 0.10
                break

    # Title-token overlap — hadiths whose kitab title words appear literally
    # in the leaf's display_name get a tiny bump
    display_tokens = set(re.findall(r'[a-z]{4,}', (leaf.get('display_name') or '').lower()))
    if display_tokens & matn_tokens:
        overlap_count = len(display_tokens & matn_tokens)
        score += min(0.08, 0.02 * overlap_count)

    return (min(score, 1.0), matched_phrases)


def enrich_one_rulebased(
    record: dict[str, Any],
    taxonomy_index: dict[str, Any],
) -> dict[str, Any]:
    """Assign leaf topic(s) to a single hadith record via deterministic rules."""
    hadith_id = record.get('hadith_id', '')
    matn_raw = record.get('matn_text') or ''
    matn_clean = clean_matn(matn_raw)
    family = record.get('query_family') or ''
    kitab = record.get('kitab_title_english') or ''
    baab = record.get('synthetic_baab_label') or ''

    base_result = {
        'hadith_id': hadith_id,
        'hadith_global_num': record.get('hadith_global_num'),
        'matn_text_clean': matn_clean,
        'enrichment_version': _ENRICHMENT_VERSION,
        'enrichment_model': _ENRICHMENT_MODEL,
    }

    if not matn_clean:
        return {
            **base_result,
            'primary_topics': [],
            'secondary_topics': [],
            'concept_vocabulary': [],
            'topic_density': 0.0,
            'is_multi_topic': False,
            'abstain_reason': 'empty_matn',
        }

    matn_tokens = set(re.findall(r'[a-z]{4,}', matn_clean.lower()))

    # ------------------------------------------------------------------
    # Layer 1 — Baab exact match
    # ------------------------------------------------------------------
    if baab and baab in taxonomy_index['baab_to_slug']:
        slug = taxonomy_index['baab_to_slug'][baab]
        leaf = taxonomy_index['leafs'][slug]
        # Compute matched_phrases for concept_vocabulary field
        regexes = taxonomy_index['leaf_regexes'].get(slug, [])
        phrases = _matched_phrases(matn_clean, regexes, leaf.get('vocabulary') or [])
        return {
            **base_result,
            'primary_topics': [slug],
            'secondary_topics': [],
            'concept_vocabulary': phrases,
            'topic_density': _DENSITY_BAAB_MATCH,
            'is_multi_topic': False,
            'abstain_reason': None,
        }

    # ------------------------------------------------------------------
    # Layer 2 — Kitab unique mapping (kitab appears in only one leaf)
    # ------------------------------------------------------------------
    if kitab:
        candidate_slugs = taxonomy_index['kitab_to_slugs'].get(kitab, [])
        if len(candidate_slugs) == 1:
            slug = candidate_slugs[0]
            leaf = taxonomy_index['leafs'][slug]
            regexes = taxonomy_index['leaf_regexes'].get(slug, [])
            phrases = _matched_phrases(matn_clean, regexes, leaf.get('vocabulary') or [])
            return {
                **base_result,
                'primary_topics': [slug],
                'secondary_topics': [],
                'concept_vocabulary': phrases,
                'topic_density': _DENSITY_KITAB_UNIQUE,
                'is_multi_topic': False,
                'abstain_reason': None,
            }

    # ------------------------------------------------------------------
    # Layer 3 — Vocabulary scoring within the matching family
    # ------------------------------------------------------------------
    candidate_slugs = taxonomy_index['family_to_slugs'].get(family) or list(taxonomy_index['leafs'].keys())

    scored: list[tuple[float, str, list[str]]] = []
    for slug in candidate_slugs:
        score, phrases = score_candidate_leaf(slug, taxonomy_index, record, matn_clean, matn_tokens)
        scored.append((score, slug, phrases))
    scored.sort(key=lambda t: -t[0])

    if not scored:
        return {
            **base_result,
            'primary_topics': [],
            'secondary_topics': [],
            'concept_vocabulary': [],
            'topic_density': 0.0,
            'is_multi_topic': False,
            'abstain_reason': 'no_family_candidates',
        }

    top_score, top_slug, top_phrases = scored[0]
    runner_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = top_score - runner_score

    # Hard abstain: top candidate simply isn't confident enough.
    if top_score < _MIN_SCORE:
        return {
            **base_result,
            'primary_topics': [],
            'secondary_topics': [],
            'concept_vocabulary': [],
            'topic_density': round(top_score, 3),
            'is_multi_topic': False,
            'abstain_reason': 'low_confidence_rulebased',
        }

    # Tie-breaking policy:
    #   · Strong confidence (top >= 0.70): accept top even with tight margin,
    #     surface near-ties as secondary_topics. Better than abstaining on a
    #     hadith that clearly belongs to a cluster of related topics (e.g.
    #     adhan vs prayer-general vs congregation).
    #   · Medium confidence (0.55 <= top < 0.70): require the original
    #     _MIN_MARGIN to accept.
    if top_score < 0.70 and margin < _MIN_MARGIN:
        return {
            **base_result,
            'primary_topics': [],
            'secondary_topics': [],
            'concept_vocabulary': [],
            'topic_density': round(top_score, 3),
            'is_multi_topic': False,
            'abstain_reason': 'low_confidence_rulebased',
        }

    secondary: list[str] = []
    for score, slug, _ in scored[1:6]:
        if score >= 0.5 and slug != top_slug and (top_score - score) <= 0.20:
            secondary.append(slug)

    density = _DENSITY_VOCAB_STRONG if top_score >= 0.8 else _DENSITY_VOCAB_MODERATE
    is_multi = len(secondary) >= 2 and scored[1][0] >= (top_score - 0.10)

    return {
        **base_result,
        'primary_topics': [top_slug],
        'secondary_topics': secondary[:5],
        'concept_vocabulary': top_phrases,
        'topic_density': density,
        'is_multi_topic': is_multi,
        'abstain_reason': None,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_source() -> list[dict[str, Any]]:
    with _SOURCE_JSON.open(encoding='utf-8') as fp:
        return json.load(fp)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Re-enrich even if already present.')
    parser.add_argument('--limit', type=int, default=0, help='Process at most N records.')
    parser.add_argument('--dry-run', action='store_true', help='Print first 5 results to stdout, do not persist.')
    parser.add_argument('--overwrite-llm', action='store_true',
                        help='Replace even LLM-enriched records. Default: only fill missing.')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')

    taxonomy = load_taxonomy()
    taxonomy_index = index_taxonomy(taxonomy)
    log.info('Taxonomy indexed: %d leafs, %d unique baab→slug rules, %d unique kitab→slug rules.',
             len(taxonomy_index['leafs']),
             len(taxonomy_index['baab_to_slug']),
             sum(1 for slugs in taxonomy_index['kitab_to_slugs'].values() if len(slugs) == 1))

    records = [r for r in load_source() if not r.get('is_stub')]
    log.info('Source corpus: %d non-stub records.', len(records))

    existing = {} if args.force else load_existing()
    if args.overwrite_llm:
        pending = records
        log.info('--overwrite-llm: processing ALL %d records regardless of prior enrichment.', len(pending))
    else:
        pending = [r for r in records if r['hadith_id'] not in existing]
        log.info('Existing enriched records: %d  |  rule-based will fill %d missing.',
                 len(existing), len(pending))

    if args.limit:
        pending = pending[: args.limit]

    if not pending:
        log.info('Nothing to do — output already complete.')
        write_report(existing, taxonomy)
        return

    if args.dry_run:
        for record in pending[:5]:
            result = enrich_one_rulebased(record, taxonomy_index)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    records_by_id: dict[str, dict[str, Any]] = dict(existing)
    start = time.time()
    abstained = 0
    by_layer = {'baab': 0, 'kitab': 0, 'vocab': 0, 'abstain': 0}

    for idx, record in enumerate(pending, start=1):
        result = enrich_one_rulebased(record, taxonomy_index)
        records_by_id[result['hadith_id']] = result

        if not result['primary_topics']:
            abstained += 1
            by_layer['abstain'] += 1
        else:
            density = result['topic_density']
            if density == _DENSITY_BAAB_MATCH:
                by_layer['baab'] += 1
            elif density == _DENSITY_KITAB_UNIQUE:
                by_layer['kitab'] += 1
            else:
                by_layer['vocab'] += 1

        if idx % 1000 == 0:
            log.info('[%d/%d]  baab=%d  kitab=%d  vocab=%d  abstain=%d  elapsed=%.1fs',
                     idx, len(pending), by_layer['baab'], by_layer['kitab'],
                     by_layer['vocab'], by_layer['abstain'], time.time() - start)

    atomic_write(records_by_id)
    log.info('Wrote %s (%d records, elapsed=%.1fs).',
             _OUT_JSON.relative_to(_REPO_ROOT), len(records_by_id), time.time() - start)
    log.info('Assignment layers for this run:  baab_exact=%d  kitab_unique=%d  vocab_scored=%d  abstained=%d (%.1f%%)',
             by_layer['baab'], by_layer['kitab'], by_layer['vocab'], by_layer['abstain'],
             100 * by_layer['abstain'] / max(1, len(pending)))

    write_report(records_by_id, taxonomy)


if __name__ == '__main__':
    main()
