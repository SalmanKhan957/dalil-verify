# Ask API Placeholder Hardening — Apply Notes

## Why this patch exists
Swagger/OpenAPI displays optional string fields with a generic `"string"` placeholder. In DALIL, source override fields are **governance-bearing inputs**, so pasting those placeholders causes a false source-override failure instead of the intended default-source path.

## What this patch changes
- Hardens `apps/ask_api/schemas.py` so obvious OpenAPI placeholder values are rejected with a clear **422** validation error.
- Updates request descriptions to tell callers to **omit** source override fields unless intentionally using a real approved source id.
- Adds explicit schema examples that **do not** include fake placeholder source ids.
- Adds regression coverage for both `/ask` and `/ask/explain` plus OpenAPI examples.

## Files in this bundle
- `apps/ask_api/schemas.py`
- `tests/integration/test_ask_api_placeholder_validation.py`

## Recommended validation
```bash
pytest
python -m pipelines.evaluation.run_quran_tafsir_acceptance
alembic upgrade head
```
