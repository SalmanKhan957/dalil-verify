# Answer Surface Cleanup Fix — Compatibility Patch

This patch corrects the two regressions from the prior answer-surface cleanup bundle.

## What changed

### 1) Quran source origin now comes from raw request presence
`explicit_override` means the caller actually supplied the override field.
`implicit_default` means DALIL selected the source by default.

### 2) Legacy `quran_source_selection` stays stable
No origin fields are added there.
Origin semantics live only under `source_policy.quran`.

## Files included
- `apps/ask_api/routes/ask.py`
- `apps/ask_api/routes/explain.py`
- `domains/ask/dispatcher.py`
- `domains/ask/workflows/explain_answer.py`
- `domains/ask/planner.py`
- `domains/ask/planner_types.py`
- `domains/answer_engine/response_builder.py`
- `apps/ask_api/schemas.py`
- `tests/integration/test_explain_answer_source_policy_surface.py`

## Validate
```bash
pytest
python -m pipelines.evaluation.run_quran_tafsir_acceptance
alembic upgrade head
```
