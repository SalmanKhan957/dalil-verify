# DALIL Answer-Surface Cleanup — Apply Notes

## What this tranche does

This bundle applies the **answer-surface cleanup** that should land **before Hadith design**.

It makes three deliberate production-level decisions:

1. **Do not break the public response contract yet.**
   - The duplicated `result` envelope is retained for backward compatibility.
   - The schema now explicitly marks it as a **legacy compatibility envelope**.
   - Retirement should happen later as a controlled API deprecation, not as a silent refactor.

2. **Stop over-promising in `answer_text` for Tafsir-backed responses.**
   - `answer_text` for `quran_with_tafsir` now stays **translation-led and coherent**.
   - DALIL no longer injects a long raw Tafsir excerpt into the primary answer line.
   - The retrieved Tafsir excerpt remains available in `tafsir_support`.

3. **Make Quran source selection more truthful.**
   - The response now distinguishes between **`explicit_override`** and **`implicit_default`** for Quran text and translation source selection.
   - This distinction is surfaced in both `quran_source_selection` and `source_policy.quran`.

## Files to replace/add

- `domains/ask/source_policy_types.py`
- `domains/ask/planner_types.py`
- `domains/policies/ask_source_policy.py`
- `domains/ask/planner.py`
- `domains/answer_engine/response_builder.py`
- `apps/ask_api/schemas.py`
- `tests/unit/test_answer_engine_composer.py`
- `tests/unit/test_ask_source_policy.py`
- `tests/integration/test_explain_answer_source_policy_surface.py`

## Validation

Run:

```bash
pytest
python -m pipelines.evaluation.run_quran_tafsir_acceptance
alembic upgrade head
```

## Manual checks

### 1) Tafsir answer text should be clean

Request:

```json
{
  "query": "Tafsir of Surah Ikhlas",
  "include_tafsir": true
}
```

Expected characteristics:
- `answer_mode == "quran_with_tafsir"`
- `answer_text` is coherent and translation-led
- `answer_text` should not dump a clipped raw Tafsir excerpt
- `tafsir_support` still includes the retrieved excerpt and HTML

### 2) Quran source origin should be honest when omitted

Request:

```json
{
  "query": "What does 112:1-4 say?"
}
```

Expected characteristics:
- `source_policy.quran.text_source_origin == "implicit_default"`
- `source_policy.quran.translation_source_origin == "implicit_default"`

### 3) Quran source origin should be explicit when overridden

Request:

```json
{
  "query": "What does 112:1-4 say?",
  "quran_text_source_id": "quran:tanzil-simple",
  "quran_translation_source_id": "quran:towards-understanding-en"
}
```

Expected characteristics:
- `source_policy.quran.text_source_origin == "explicit_override"`
- `source_policy.quran.translation_source_origin == "explicit_override"`
