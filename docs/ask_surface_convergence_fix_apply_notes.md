# Ask Surface Convergence Fix — Apply Notes

## Purpose
Restore the `apps.ask_api.routes.explain.explain_answer` symbol as a compatibility wrapper while keeping `/ask/explain` on the shared Ask dispatch path.

## Why this is needed
A contract/integration test monkeypatches `apps.ask_api.routes.explain.explain_answer` directly. The convergence refactor removed that symbol and caused a compatibility failure even though the shared dispatch behavior was otherwise correct.

## Apply
Replace:
- `apps/ask_api/routes/explain.py`

## Validate
Run:

```bash
pytest
python -m pipelines.evaluation.run_quran_tafsir_acceptance
alembic upgrade head
```
