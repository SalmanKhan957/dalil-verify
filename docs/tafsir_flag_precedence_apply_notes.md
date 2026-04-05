# Ask API Tafsir Flag Precedence Hardening

## Objective
Make explicit API intent win over natural-language tafsir wording.

## Contract after this patch
- `include_tafsir=true` -> include Tafsir when eligible.
- `include_tafsir=false` -> suppress Tafsir even if the query says things like `Tafsir of Surah Ikhlas`.
- `include_tafsir` omitted / `null` -> let current query-intent routing decide.

## Files in this bundle
- `domains/ask/planner.py`
- `tests/unit/test_answer_engine_planner.py`

## Why this patch exists
The current routed behavior is fine for conversational intent, but it is not a clean API contract. When a caller sets `include_tafsir=false`, the boolean should outrank the prose query.

## Apply
Replace the files at the same repo-relative paths, then run:

```bash
pytest
python -m pipelines.evaluation.run_quran_tafsir_acceptance
alembic upgrade head
```

## Manual verification
This request should now return a Quran-only explanation path with no Tafsir support:

```json
{
  "query": "Tafsir of Surah Ikhlas",
  "include_tafsir": false
}
```

This request should still include Tafsir:

```json
{
  "query": "Tafsir of Surah Ikhlas",
  "include_tafsir": true
}
```
