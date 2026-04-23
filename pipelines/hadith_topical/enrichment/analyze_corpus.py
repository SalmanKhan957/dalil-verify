"""Corpus analysis for bottom-up Bukhari topic taxonomy drafting.

Produces an auditable view of the corpus structured as:

    query_family → (kitab_title, synthetic_baab_label) bucket
                 → distinctive TF-IDF terms
                 → sample matn_texts

The output (JSON + human-readable markdown) is what a human reviewer reads
when authoring `assets/hadith_topical/bukhari_topic_taxonomy.v1.json`.

No LLM / network calls. Pure stdlib + numpy.

Usage:
    python -m pipelines.hadith_topical.enrichment.analyze_corpus
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SOURCE_JSON = _REPO_ROOT / 'data' / 'raw' / 'hadith' / 'meeatif' / 'bukhari_enriched_v3.json'
_OUT_DIR = _REPO_ROOT / 'pipelines' / 'hadith_topical' / 'enrichment' / 'output'
_OUT_JSON = _OUT_DIR / 'corpus_analysis.json'
_OUT_MD = _OUT_DIR / 'corpus_analysis.md'

# Minimal English stopwords; we want distinctive content words to surface.
_STOP = frozenset("""
a an and or but if then else when while because although though for to of in on at by with from into onto about over under above below up down off out
is are was were be been being am do does did doing have has had having will would could should may might must can shall
i you he she it we they them him her us me my your his its our their this that these those which who whom whose what
not no nor so as than also too very just only even already ever never always sometimes often rarely some any all most more less few many much
said says saying told telling asked asking replied replying narrated reported narrator prophet allah messenger apostle sahih
one two three four five six seven eight nine ten ﷺ pbuh
""".split())

_TOKEN_RE = re.compile(r"[A-Za-z]{3,}")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or '') if t.lower() not in _STOP]


def _strip_embedded_narrators(matn: str) -> str:
    """Remove 'Narrated X:' sentences that leak narrator strings into matn_text."""
    return re.sub(r'Narrated\s+[^:]{2,80}:', ' ', matn, flags=re.IGNORECASE)


def _load_corpus() -> list[dict[str, Any]]:
    with _SOURCE_JSON.open(encoding='utf-8') as fp:
        return json.load(fp)


def _compute_family_tfidf(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Per family, return {term: idf_weight} restricted to the family's docs."""
    family_docs: dict[str, list[list[str]]] = defaultdict(list)
    for record in records:
        if record.get('is_stub'):
            continue
        family = record.get('query_family') or 'unknown'
        clean = _strip_embedded_narrators(record.get('matn_text') or '')
        family_docs[family].append(_tokenize(clean))

    family_idf: dict[str, dict[str, float]] = {}
    for family, docs in family_docs.items():
        n = len(docs)
        df = Counter()
        for tokens in docs:
            for term in set(tokens):
                df[term] += 1
        family_idf[family] = {
            term: math.log((n + 1) / (count + 1)) + 1.0
            for term, count in df.items()
        }
    return family_idf


def _distinctive_terms(
    tokens: list[str],
    family_idf: dict[str, float],
    top_n: int = 8,
) -> list[tuple[str, float]]:
    tf = Counter(tokens)
    scored = [
        (term, (count / max(1, len(tokens))) * family_idf.get(term, 1.0))
        for term, count in tf.items()
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_n]


def _bucket_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        record.get('query_family') or 'unknown',
        record.get('kitab_title_english') or 'unknown',
        record.get('synthetic_baab_label') or 'unknown',
    )


def _short_preview(matn: str, limit: int = 180) -> str:
    cleaned = ' '.join((matn or '').split())
    return cleaned[:limit] + ('…' if len(cleaned) > limit else '')


def build_analysis() -> dict[str, Any]:
    records = _load_corpus()
    records = [r for r in records if not r.get('is_stub')]
    family_idf = _compute_family_tfidf(records)

    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        buckets[_bucket_key(record)].append(record)

    family_to_kitabs: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))

    for (family, kitab, baab), bucket_records in buckets.items():
        tokens_in_bucket: list[str] = []
        for record in bucket_records:
            tokens_in_bucket.extend(_tokenize(_strip_embedded_narrators(record.get('matn_text') or '')))

        distinctive = _distinctive_terms(tokens_in_bucket, family_idf.get(family, {}), top_n=10)

        representative = sorted(
            bucket_records,
            key=lambda r: len(r.get('matn_text') or ''),
        )
        sample_refs = representative[: min(6, len(representative))]

        baab_block = {
            'record_count': len(bucket_records),
            'has_direct_prophetic_statement_count': sum(
                1 for r in bucket_records if r.get('has_direct_prophetic_statement')
            ),
            'distinctive_terms': [term for term, _ in distinctive],
            'distinctive_terms_scored': [
                {'term': term, 'score': round(score, 4)} for term, score in distinctive
            ],
            'sample_hadith_ids': [r.get('hadith_id') for r in sample_refs],
            'sample_matn_previews': [
                {
                    'hadith_id': r.get('hadith_id'),
                    'is_prophetic': bool(r.get('has_direct_prophetic_statement')),
                    'preview': _short_preview(r.get('matn_text') or ''),
                }
                for r in sample_refs
            ],
        }
        family_to_kitabs[family][kitab][baab] = baab_block

    analysis = {
        'source_file': str(_SOURCE_JSON.relative_to(_REPO_ROOT)),
        'total_records': len(records),
        'families': {},
    }
    for family, kitabs in family_to_kitabs.items():
        family_records = sum(b['record_count'] for kitab in kitabs.values() for b in kitab.values())
        analysis['families'][family] = {
            'record_count': family_records,
            'kitab_count': len(kitabs),
            'kitabs': {
                kitab: {
                    'record_count': sum(b['record_count'] for b in baabs.values()),
                    'baabs': baabs,
                }
                for kitab, baabs in sorted(
                    kitabs.items(),
                    key=lambda pair: -sum(b['record_count'] for b in pair[1].values()),
                )
            },
        }
    return analysis


def render_markdown(analysis: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Bukhari corpus analysis — taxonomy drafting aid")
    lines.append('')
    lines.append(f"Source: `{analysis['source_file']}`  |  Total non-stub records: **{analysis['total_records']}**")
    lines.append('')
    families = analysis['families']
    family_order = sorted(families.items(), key=lambda pair: -pair[1]['record_count'])
    for family, fdata in family_order:
        lines.append(f"## Family: `{family}` — {fdata['record_count']} records across {fdata['kitab_count']} kitabs")
        lines.append('')
        for kitab, kdata in fdata['kitabs'].items():
            lines.append(f"### Kitab: *{kitab}* — {kdata['record_count']} records")
            lines.append('')
            for baab, bdata in sorted(kdata['baabs'].items(), key=lambda pair: -pair[1]['record_count']):
                lines.append(f"**Baab:** `{baab}` — {bdata['record_count']} records ({bdata['has_direct_prophetic_statement_count']} prophetic)")
                lines.append('')
                lines.append(f"  - Distinctive terms: `{', '.join(bdata['distinctive_terms'])}`")
                for sample in bdata['sample_matn_previews']:
                    marker = '⚡' if sample['is_prophetic'] else ' '
                    lines.append(f"  - {marker} `{sample['hadith_id']}`: {sample['preview']}")
                lines.append('')
        lines.append('')
    return '\n'.join(lines)


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    analysis = build_analysis()
    _OUT_JSON.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
    _OUT_MD.write_text(render_markdown(analysis), encoding='utf-8')
    print(f"Wrote {_OUT_JSON.relative_to(_REPO_ROOT)}")
    print(f"Wrote {_OUT_MD.relative_to(_REPO_ROOT)}")
    print()
    print(f"Families: {len(analysis['families'])}")
    for family, fdata in sorted(analysis['families'].items(), key=lambda p: -p[1]['record_count']):
        print(f"  {family:15s}: {fdata['record_count']:4d} records, {fdata['kitab_count']:3d} kitabs")


if __name__ == '__main__':
    main()
