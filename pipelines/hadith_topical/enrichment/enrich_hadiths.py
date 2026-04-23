"""Per-hadith topical enrichment for Sahih al-Bukhari.

Given:
    assets/hadith_topical/bukhari_topic_taxonomy.v1.json
    data/raw/hadith/meeatif/bukhari_enriched_v3.json

Produces:
    data/raw/hadith/meeatif/bukhari_enriched_v3_topical.json

For each non-stub hadith, calls OpenAI (gpt-4o-mini) with the taxonomy as a
cached system prompt and emits a structured JSON decision:

    {
      "hadith_id": "bukhari:3356",
      "primary_topics": ["historical.prophets.ibrahim", "fiqh.food.hunting_slaughter"],
      "secondary_topics": [],
      "concept_vocabulary": ["Abraham", "circumcision"],
      "topic_density": 0.78,
      "is_multi_topic": false,
      "abstain_reason": null,
      "matn_text_clean": "Allah's Messenger ... at the age of eighty.",
      "enrichment_version": "v1",
      "enrichment_model": "gpt-4o-mini"
    }

Design principles:

    * matn_text is cleaned (embedded "Narrated X:" fragments removed) BEFORE being
      shown to the LLM. This prevents narrator-name substrings (Abu Az-Zinad) from
      poisoning the zina-query path — the fix lives in the data, not at runtime.
    * Every primary_topics slug is validated against the taxonomy; invalid slugs
      force a retry with a stricter prompt.
    * Resume-safe: already-enriched hadith_ids are skipped on rerun. Output is
      written atomically (temp file + rename) every CHECKPOINT_EVERY records so
      a crash loses at most 50 records of work.
    * Concurrency bounded by CONCURRENCY (default 10) with exponential backoff
      on 429 / 5xx.
    * Deterministic (temperature=0). Same input → same output.

Usage:
    python -m pipelines.hadith_topical.enrichment.enrich_hadiths
    python -m pipelines.hadith_topical.enrichment.enrich_hadiths --dry-run 20
    python -m pipelines.hadith_topical.enrichment.enrich_hadiths --limit 100
    python -m pipelines.hadith_topical.enrichment.enrich_hadiths --force
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SOURCE_JSON = _REPO_ROOT / 'data' / 'raw' / 'hadith' / 'meeatif' / 'bukhari_enriched_v3.json'
_TAXONOMY_JSON = _REPO_ROOT / 'assets' / 'hadith_topical' / 'bukhari_topic_taxonomy.v1.json'
_OUT_JSON = _REPO_ROOT / 'data' / 'raw' / 'hadith' / 'meeatif' / 'bukhari_enriched_v3_topical.json'
_REPORT_MD = _REPO_ROOT / 'pipelines' / 'hadith_topical' / 'enrichment' / 'output' / 'enrichment_report.md'

_OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
_MODEL = 'gpt-4o-mini'
_ENRICHMENT_VERSION = 'v1'
_DEFAULT_CONCURRENCY = 10
_CHECKPOINT_EVERY = 50
_DEFAULT_MAX_RETRIES = 8
_REQUEST_TIMEOUT = 60.0
_MAX_BACKOFF_SECONDS = 60.0

log = logging.getLogger('enrich_hadiths')


# ---------------------------------------------------------------------------
# Matn cleaning — narrator leak prevention at the data layer
# ---------------------------------------------------------------------------

_NARRATED_PATTERN = re.compile(r'Narrated\s+[^:]{2,80}:', re.IGNORECASE)


def clean_matn(matn: str) -> str:
    """Strip 'Narrated X:' secondary narrator attributions.

    The raw Bukhari English translation often embeds a secondary narrator as
    "Narrated Abu Az-Zinad: (as above)" inside the matn of an already-attributed
    hadith. That pattern is what makes 'zina' queries collide with Abu Az-Zinad.
    We remove the pattern once, at enrichment time, and store the cleaned
    string alongside the raw one. The runtime index uses the cleaned field.
    """
    return re.sub(r'\s+', ' ', _NARRATED_PATTERN.sub(' ', matn or '')).strip()


# ---------------------------------------------------------------------------
# Taxonomy plumbing
# ---------------------------------------------------------------------------

def load_taxonomy() -> dict[str, Any]:
    with _TAXONOMY_JSON.open(encoding='utf-8') as fp:
        return json.load(fp)


def compact_taxonomy_for_prompt(taxonomy: dict[str, Any]) -> str:
    """Render the taxonomy as a compact JSON string for the system prompt.

    Drops `source_kitabs` / `source_baabs` (locator aids only, not needed for
    LLM decision) to keep the cached prefix tight.
    """
    leafs = {}
    for slug, entry in taxonomy['leaf_topics'].items():
        compact = {
            'family': entry['family'],
            'name': entry['display_name'],
            'vocabulary': entry['vocabulary'],
        }
        if entry.get('disambiguation_hint'):
            compact['hint'] = entry['disambiguation_hint']
        leafs[slug] = compact
    return json.dumps({'leaf_topics': leafs}, ensure_ascii=False, separators=(',', ':'))


def build_system_prompt(taxonomy: dict[str, Any]) -> str:
    compact = compact_taxonomy_for_prompt(taxonomy)
    return (
        'You are the DALIL Bukhari topical enrichment engine. For each hadith I give you, '
        'you assign leaf topic slugs drawn EXCLUSIVELY from the taxonomy below and emit '
        'a strict JSON decision.\n\n'
        'Rules:\n'
        '1. `primary_topics` contains 1 to 3 slugs. Every slug MUST exist in the taxonomy. '
        'Never invent slugs. Never abbreviate.\n'
        '2. PREFER ASSIGNMENT. When the hadith has any narrative, ruling, or prophetic '
        'statement of meaningful length, pick at least one leaf that fits approximately — '
        'even if the fit is not perfect. Approximate fit is better than abstention for '
        'retrieval. Only abstain (empty `primary_topics` + `abstain_reason`) when: '
        '(a) `matn_too_fragmentary` — the text is a stub like "(as above)" or a 3-word '
        'clause with no thematic anchor; (b) `incidental_mention_only` — the topic appears '
        'in passing as part of an unrelated narration; (c) `no_taxonomy_fit` — after genuine '
        'effort, nothing in the 182-leaf taxonomy is even approximately aligned.\n'
        '3. `secondary_topics` is 0 to 5 additional slugs for topics the hadith also '
        'touches but is not centrally about. Must also exist in the taxonomy.\n'
        '4. `concept_vocabulary` lists UP TO 6 short phrases drawn LITERALLY from the '
        'hadith text that a user could plausibly search for. Use the phrases as they appear '
        '(lowercase, stripped). No paraphrasing.\n'
        '5. `topic_density` is a float in [0.0, 1.0] estimating how central the primary '
        'topic is to the hadith. 0.9+ = the hadith is squarely about the topic. '
        '0.5–0.8 = topic is one of several themes. <0.5 = topic is incidental, prefer abstain.\n'
        '6. `is_multi_topic` is true when the hadith genuinely covers two or more distinct '
        'topics with comparable weight.\n'
        '7. Never use the narrator name or the `Narrated X:` framing to decide the topic. '
        'Decide ONLY from the matn (the prophetic statement and its immediate context).\n'
        '8. Output strictly the JSON object. No markdown, no commentary.\n\n'
        'Output schema:\n'
        '{"primary_topics":["slug"],"secondary_topics":["slug"],"concept_vocabulary":["phrase"],'
        '"topic_density":0.0,"is_multi_topic":false,"abstain_reason":null}\n\n'
        'Taxonomy:\n' + compact
    )


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

def _api_key() -> str:
    key = os.getenv('OPENAI_API_KEY') or ''
    if not key.strip():
        # Try settings module as fallback
        try:
            from infrastructure.config.settings import settings  # type: ignore
            key = (settings.openai_api_key or '').strip()
        except Exception:
            pass
    if not key.strip():
        log.error('OPENAI_API_KEY not set in env or settings.')
        sys.exit(2)
    return key.strip()


def build_user_message(record: dict[str, Any], cleaned_matn: str) -> str:
    return json.dumps({
        'hadith_id': record['hadith_id'],
        'query_family_hint': record.get('query_family') or '',
        'synthetic_baab_label_hint': record.get('synthetic_baab_label') or '',
        'kitab_title': record.get('kitab_title_english') or '',
        'narrator': (record.get('narrator') or '').strip() or None,
        'matn_text': cleaned_matn,
        'has_direct_prophetic_statement': bool(record.get('has_direct_prophetic_statement')),
    }, ensure_ascii=False)


def call_openai(
    system_prompt: str,
    user_message: str,
    api_key: str,
) -> dict[str, Any]:
    payload = {
        'model': _MODEL,
        'temperature': 0.0,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
    }
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        _OPENAI_URL,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        response_body = json.loads(resp.read().decode('utf-8'))
    content = response_body['choices'][0]['message']['content']
    return json.loads(content)


def call_with_retry(
    system_prompt: str,
    user_message: str,
    api_key: str,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return call_openai(system_prompt, user_message, api_key)
        except urllib.error.HTTPError as exc:
            last_error = exc
            status = exc.code
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            if status in (429, 500, 502, 503, 504):
                try:
                    header_backoff = float(retry_after) if retry_after else 0.0
                except (TypeError, ValueError):
                    header_backoff = 0.0
                backoff = max(header_backoff, min(_MAX_BACKOFF_SECONDS, 2 ** attempt)) + random.uniform(0, 1)
                log.warning('HTTP %s on attempt %d/%d; retrying in %.1fs', status, attempt + 1, max_retries, backoff)
                time.sleep(backoff)
                continue
            log.error('Non-retryable HTTP %s: %s', status, exc.read().decode('utf-8', errors='replace')[:400])
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            backoff = min(_MAX_BACKOFF_SECONDS / 2, 2 ** attempt) + random.uniform(0, 1)
            log.warning('Transient error on attempt %d/%d: %s; retrying in %.1fs', attempt + 1, max_retries, exc, backoff)
            time.sleep(backoff)
            continue
    raise RuntimeError(f'Exhausted retries; last error: {last_error}')


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ValidationResult:
    ok: bool
    message: str = ''


def _build_slug_suffix_index(taxonomy_slugs: set[str]) -> dict[str, str]:
    """Build a unique-suffix → full-slug map for LLM auto-correction.

    The LLM occasionally emits `fiqh.hajj.general` when the taxonomy has
    `ritual.hajj.general`. Picking the wrong family prefix but the right
    leaf is a common recoverable error. We index every dot-suffix and,
    when exactly one taxonomy slug shares that suffix, auto-correct.
    """
    suffix_counts: dict[str, int] = {}
    suffix_to_slug: dict[str, str] = {}
    for slug in taxonomy_slugs:
        parts = slug.split('.')
        for i in range(1, len(parts)):
            suffix = '.'.join(parts[i:])
            suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
            suffix_to_slug[suffix] = slug
    return {suffix: slug for suffix, slug in suffix_to_slug.items() if suffix_counts[suffix] == 1}


def _autocorrect_slug(
    raw: str,
    taxonomy_slugs: set[str],
    suffix_index: dict[str, str],
) -> str | None:
    """Return a valid slug for a raw LLM output, or None if uncorrectable.

    Correction layers (first match wins):
        1. Exact match — the raw slug is already valid.
        2. Unique-suffix match — the LLM used the wrong family prefix but
           the leaf name is unique (e.g. fiqh.hajj.general → ritual.hajj.general).
        3. Family + area → general — the LLM invented a leaf but the
           family and area prefix map to a valid `<family>.<area>.general`
           leaf (e.g. ritual.hajj.jamarat_stoning → ritual.hajj.general).
           This degrades specificity but keeps the record retrievable.
        4. Family + area prefix — any valid slug starting with `<family>.<area>.`
           if exactly one exists (captures sawm.suhur → sawm.fasting_general
           when that's the only sawm-area leaf matching).
    """
    if raw in taxonomy_slugs:
        return raw
    parts = raw.split('.')

    # Layer 2: unique suffix
    for i in range(1, len(parts)):
        suffix = '.'.join(parts[i:])
        if suffix in suffix_index:
            return suffix_index[suffix]

    # Layer 3: family.area.general fallback
    if len(parts) >= 2:
        general_candidate = f'{parts[0]}.{parts[1]}.general'
        if general_candidate in taxonomy_slugs:
            return general_candidate

    # Layer 4: unique leaf under family.area.*
    if len(parts) >= 2:
        prefix = f'{parts[0]}.{parts[1]}.'
        matches = [s for s in taxonomy_slugs if s.startswith(prefix)]
        if len(matches) == 1:
            return matches[0]

    # Layer 5: family.area has a `*_general` catch-all (e.g. sawm.fasting_general)
    if len(parts) >= 2:
        prefix = f'{parts[0]}.{parts[1]}.'
        general_like = [
            s for s in taxonomy_slugs
            if s.startswith(prefix) and s.split('.')[-1].endswith('_general')
        ]
        if len(general_like) == 1:
            return general_like[0]

    # Layer 6: family.area has a literal 'other' / 'others' catch-all
    # (e.g. historical.prophets.yusuf -> historical.prophets.other)
    if len(parts) >= 2:
        for suffix_word in ('other', 'others'):
            candidate = f'{parts[0]}.{parts[1]}.{suffix_word}'
            if candidate in taxonomy_slugs:
                return candidate

    return None


def validate_decision(
    decision: dict[str, Any],
    taxonomy_slugs: set[str],
    suffix_index: dict[str, str] | None = None,
) -> ValidationResult:
    """Permissive validator — cleans and normalises the LLM response in-place.

    Philosophy:
        * Autocorrect every slug via the fallback cascade.
        * Drop slugs that cannot be corrected (log them, but never reject the whole record).
        * If primary becomes empty after cleanup, promote the first valid secondary.
        * Soft-truncate over-long lists.
        * Only the LLM itself can produce a `genuine_abstain` — an empty
          primary with an abstain_reason emitted by the model.
        * Hard-fail ONLY on shape violations (missing keys, wrong types, bad density).
    """
    required = {'primary_topics', 'secondary_topics', 'concept_vocabulary', 'topic_density', 'is_multi_topic', 'abstain_reason'}
    missing = required - set(decision.keys())
    if missing:
        return ValidationResult(False, f'missing keys: {sorted(missing)}')

    primary = decision.get('primary_topics') or []
    secondary = decision.get('secondary_topics') or []
    vocab = decision.get('concept_vocabulary') or []

    if not isinstance(primary, list) or not isinstance(secondary, list) or not isinstance(vocab, list):
        return ValidationResult(False, 'primary/secondary/vocabulary must be lists')

    # Clean + autocorrect slugs. Invalid ones are dropped (not rejected).
    def clean_slug_list(raw: list[Any]) -> tuple[list[str], list[str], list[str]]:
        kept: list[str] = []
        dropped: list[str] = []
        corrections: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                dropped.append(repr(item))
                continue
            if item in taxonomy_slugs:
                kept.append(item)
                continue
            fixed = _autocorrect_slug(item, taxonomy_slugs, suffix_index or {}) if suffix_index is not None else None
            if fixed is not None:
                kept.append(fixed)
                corrections.append(f'{item}->{fixed}')
            else:
                dropped.append(item)
        return kept, dropped, corrections

    primary, dropped_p, corrections_p = clean_slug_list(primary)
    secondary, dropped_s, corrections_s = clean_slug_list(secondary)

    if corrections_p or corrections_s:
        log.info('Autocorrected slugs: %s', ', '.join(corrections_p + corrections_s))
    if dropped_p or dropped_s:
        log.info('Dropped uncorrectable slugs: primary=%s secondary=%s', dropped_p, dropped_s)

    # Dedupe: don't repeat primary entries in secondary.
    primary_set = set(primary)
    secondary = [s for s in secondary if s not in primary_set]
    # Dedupe within each list while preserving order.
    seen_p: set[str] = set()
    primary = [s for s in primary if not (s in seen_p or seen_p.add(s))]
    seen_s: set[str] = set()
    secondary = [s for s in secondary if not (s in seen_s or seen_s.add(s))]

    # If all primary slugs got dropped but secondary has something valid,
    # promote the first secondary to primary so the record is still useful.
    if not primary and secondary:
        promoted = secondary.pop(0)
        primary = [promoted]
        log.info('Promoted secondary to primary: %s', promoted)

    # Soft-truncate length limits.
    if len(primary) > 3:
        primary = primary[:3]
    if len(secondary) > 5:
        secondary = secondary[:5]
    if len(vocab) > 6:
        vocab = vocab[:6]

    decision['primary_topics'] = primary
    decision['secondary_topics'] = secondary
    decision['concept_vocabulary'] = vocab

    # Density range check — hard-fail shape violation.
    density = decision.get('topic_density')
    if not isinstance(density, (int, float)) or not (0.0 <= float(density) <= 1.0):
        return ValidationResult(False, f'topic_density out of range: {density!r}')

    # Clear any stale abstain_reason when the record has valid primary topics.
    # The LLM sometimes emits both primary_topics and an abstain_reason as a
    # half-committed hedge; downstream tooling should see exactly one state.
    if primary and decision.get('abstain_reason'):
        decision['abstain_reason'] = None

    # If primary is still empty after cleanup, make sure there's an abstain reason
    # so the record is still valid JSON. Never reject — we have a useful record.
    if not primary and not decision.get('abstain_reason'):
        decision['abstain_reason'] = 'all_slugs_uncorrectable'

    return ValidationResult(True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def load_source() -> list[dict[str, Any]]:
    with _SOURCE_JSON.open(encoding='utf-8') as fp:
        return json.load(fp)


def load_existing() -> dict[str, dict[str, Any]]:
    if not _OUT_JSON.exists():
        return {}
    try:
        with _OUT_JSON.open(encoding='utf-8') as fp:
            records = json.load(fp)
        return {r['hadith_id']: r for r in records if r.get('hadith_id')}
    except Exception as exc:
        log.warning('Could not read existing output (%s); starting fresh.', exc)
        return {}


def atomic_write(records_by_id: dict[str, dict[str, Any]]) -> None:
    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp = _OUT_JSON.with_suffix('.json.tmp')
    ordered = sorted(records_by_id.values(), key=lambda r: int(r.get('hadith_global_num') or 0) or r.get('hadith_id', ''))
    tmp.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(_OUT_JSON)


def enrich_one(
    record: dict[str, Any],
    system_prompt: str,
    api_key: str,
    taxonomy_slugs: set[str],
    max_retries: int = _DEFAULT_MAX_RETRIES,
    suffix_index: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    cleaned = clean_matn(record.get('matn_text') or '')
    if not cleaned:
        return {
            'hadith_id': record['hadith_id'],
            'hadith_global_num': record.get('hadith_global_num'),
            'primary_topics': [],
            'secondary_topics': [],
            'concept_vocabulary': [],
            'topic_density': 0.0,
            'is_multi_topic': False,
            'abstain_reason': 'empty_matn',
            'matn_text_clean': '',
            'enrichment_version': _ENRICHMENT_VERSION,
            'enrichment_model': _MODEL,
        }

    user_message = build_user_message(record, cleaned)

    # The validator is now permissive: it autocorrects, drops uncorrectable
    # slugs, promotes secondary to primary when needed, and only hard-fails
    # on shape violations (missing keys, wrong types, bad density). We retry
    # once on those — malformed JSON from the model is the only real failure mode.
    for attempt in range(2):
        decision = call_with_retry(system_prompt, user_message, api_key, max_retries=max_retries)
        result = validate_decision(decision, taxonomy_slugs, suffix_index=suffix_index)
        if result.ok:
            break
        log.warning('Shape-validation failed for %s (%s); retrying', record['hadith_id'], result.message)
    else:
        log.error('Response shape still invalid for %s; storing abstain.', record['hadith_id'])
        decision = {
            'primary_topics': [],
            'secondary_topics': [],
            'concept_vocabulary': [],
            'topic_density': 0.0,
            'is_multi_topic': False,
            'abstain_reason': 'validation_failed',
        }

    return {
        'hadith_id': record['hadith_id'],
        'hadith_global_num': record.get('hadith_global_num'),
        'primary_topics': decision['primary_topics'],
        'secondary_topics': decision['secondary_topics'],
        'concept_vocabulary': decision['concept_vocabulary'],
        'topic_density': float(decision['topic_density']),
        'is_multi_topic': bool(decision['is_multi_topic']),
        'abstain_reason': decision.get('abstain_reason'),
        'matn_text_clean': cleaned,
        'enrichment_version': _ENRICHMENT_VERSION,
        'enrichment_model': _MODEL,
    }


def write_report(records_by_id: dict[str, dict[str, Any]], taxonomy: dict[str, Any]) -> None:
    from collections import Counter
    total = len(records_by_id)
    abstained = [r for r in records_by_id.values() if not r['primary_topics']]
    density_dist = [r['topic_density'] for r in records_by_id.values() if r['primary_topics']]

    topic_counts = Counter()
    for r in records_by_id.values():
        for slug in r['primary_topics']:
            topic_counts[slug] += 1

    taxonomy_slugs = set(taxonomy['leaf_topics'].keys())
    empty_topics = sorted(taxonomy_slugs - set(topic_counts.keys()))

    lines: list[str] = []
    lines.append('# Bukhari enrichment report — v1')
    lines.append('')
    lines.append(f'Total enriched records: **{total}**')
    lines.append(f'Abstained (no primary topic): **{len(abstained)}** ({100 * len(abstained) / max(1, total):.1f}%)')
    lines.append('')
    if density_dist:
        import statistics
        lines.append('Topic density distribution (non-abstain):')
        lines.append(f'- min={min(density_dist):.2f}  p25={statistics.quantiles(density_dist, n=4)[0]:.2f}  median={statistics.median(density_dist):.2f}  p75={statistics.quantiles(density_dist, n=4)[2]:.2f}  max={max(density_dist):.2f}')
    lines.append('')
    lines.append('## Top 30 topics by record count')
    for slug, count in topic_counts.most_common(30):
        display = taxonomy['leaf_topics'][slug]['display_name']
        lines.append(f'- `{slug}` — **{count}** — {display}')
    lines.append('')
    lines.append(f'## Under-populated topics (<5 records): {sum(1 for _, c in topic_counts.items() if c < 5)}')
    for slug, count in sorted(topic_counts.items(), key=lambda p: p[1]):
        if count < 5:
            lines.append(f'- `{slug}` — {count}')
    lines.append('')
    lines.append(f'## Unused taxonomy slugs: {len(empty_topics)}')
    for slug in empty_topics:
        lines.append(f'- `{slug}`')
    lines.append('')
    lines.append('## Canonical test-case coverage')
    for query_topic, test_slugs in [
        ('zina', ['fiqh.hudood.zina_adultery']),
        ('dajjal', ['eschatology.dajjal']),
        ('riba/usury', ['fiqh.business.riba_usury']),
        ('backbiting', ['akhlaq.adab.backbiting_ghayba']),
        ('anger', ['akhlaq.adab.anger_control']),
        ('intention/niyya', ['foundational.intention_niyya']),
        ('prayer times', ['ritual.salah.times_of_prayer']),
        ('patience', ['akhlaq.adab.patience_sabr']),
        ('theft', ['fiqh.hudood.theft_sariqa']),
        ('paradise', ['eschatology.paradise_jannah']),
    ]:
        count = sum(topic_counts.get(s, 0) for s in test_slugs)
        lines.append(f'- **{query_topic}**: {count} records → slugs {test_slugs}')
    _REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_MD.write_text('\n'.join(lines), encoding='utf-8')
    log.info('Wrote %s', _REPORT_MD.relative_to(_REPO_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', type=int, default=0, help='Enrich only the first N records, write to stdout, do not persist.')
    parser.add_argument('--limit', type=int, default=0, help='Process at most N records (useful for testing).')
    parser.add_argument('--force', action='store_true', help='Re-enrich even if already present in output.')
    parser.add_argument('--upgrade-rulebased', action='store_true',
                        help='Re-enrich only records whose enrichment_version is "v1-rulebased", replacing them with LLM output. Preserves existing LLM records.')
    parser.add_argument('--concurrency', type=int, default=_DEFAULT_CONCURRENCY, help='Parallel OpenAI requests. Lower this on rate limits (try 3).')
    parser.add_argument('--max-retries', type=int, default=_DEFAULT_MAX_RETRIES, help='Max retries per record on 429/5xx. Higher = more tolerant of rate limits.')
    parser.add_argument('--request-interval-ms', type=int, default=0, help='Minimum ms between request submissions. Set 400–800 to stay under TPM limits.')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
    )

    taxonomy = load_taxonomy()
    taxonomy_slugs = set(taxonomy['leaf_topics'].keys())
    suffix_index = _build_slug_suffix_index(taxonomy_slugs)
    system_prompt = build_system_prompt(taxonomy)
    log.info('Taxonomy loaded: %d leaf topics. System prompt: %d chars. Autocorrect suffixes: %d.',
             len(taxonomy_slugs), len(system_prompt), len(suffix_index))

    records = [r for r in load_source() if not r.get('is_stub')]
    log.info('Source corpus: %d non-stub records.', len(records))

    existing = {} if args.force else load_existing()
    log.info('Existing enriched records: %d (will be skipped unless --force or --upgrade-rulebased).', len(existing))

    if args.force:
        pending = records
    elif args.upgrade_rulebased:
        rulebased_ids = {
            hid for hid, rec in existing.items()
            if str(rec.get('enrichment_version') or '').endswith('-rulebased')
            or str(rec.get('enrichment_model') or '').startswith('rulebased:')
        }
        pending = [r for r in records if r['hadith_id'] in rulebased_ids or r['hadith_id'] not in existing]
        log.info('Upgrade mode: %d rule-based records + %d missing records queued for LLM.',
                 len(rulebased_ids), sum(1 for r in records if r['hadith_id'] not in existing))
    else:
        pending = [r for r in records if r['hadith_id'] not in existing]

    if args.limit:
        pending = pending[: args.limit]
    if args.dry_run:
        pending = pending[: args.dry_run]
    log.info('Records to process this run: %d.', len(pending))

    if args.dry_run:
        api_key = _api_key()
        for record in pending:
            result = enrich_one(record, system_prompt, api_key, taxonomy_slugs, max_retries=args.max_retries, suffix_index=suffix_index)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not pending:
        log.info('Nothing to do.')
        write_report(existing, taxonomy)
        return

    api_key = _api_key()
    records_by_id: dict[str, dict[str, Any]] = dict(existing)
    processed_since_checkpoint = 0
    checkpoint_lock = threading.Lock()
    submit_lock = threading.Lock()
    last_submit = [0.0]
    interval = max(0, args.request_interval_ms) / 1000.0

    def worker(record: dict[str, Any]) -> dict[str, Any]:
        if interval > 0:
            with submit_lock:
                wait = (last_submit[0] + interval) - time.time()
                if wait > 0:
                    time.sleep(wait)
                last_submit[0] = time.time()
        return enrich_one(record, system_prompt, api_key, taxonomy_slugs, max_retries=args.max_retries, suffix_index=suffix_index)

    log.info('Running with concurrency=%d max_retries=%d request_interval_ms=%d',
             args.concurrency, args.max_retries, args.request_interval_ms)
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker, record): record for record in pending}
        for idx, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            try:
                result = future.result()
            except Exception as exc:
                record = futures[future]
                log.error('Failed to enrich %s: %s', record.get('hadith_id'), exc)
                continue
            if result is None:
                continue
            with checkpoint_lock:
                records_by_id[result['hadith_id']] = result
                processed_since_checkpoint += 1
                if processed_since_checkpoint >= _CHECKPOINT_EVERY:
                    atomic_write(records_by_id)
                    processed_since_checkpoint = 0
                    elapsed = time.time() - start
                    log.info('[%d/%d]  elapsed=%.0fs  rate=%.2f/s  last=%s',
                             idx, len(pending), elapsed, idx / elapsed, result['hadith_id'])

    atomic_write(records_by_id)
    log.info('Final output written to %s (%d records).', _OUT_JSON.relative_to(_REPO_ROOT), len(records_by_id))
    write_report(records_by_id, taxonomy)


if __name__ == '__main__':
    main()
