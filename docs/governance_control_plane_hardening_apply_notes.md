# Governance Control-Plane Hardening — Apply Notes

## Goal
Centralize bounded Ask/Quran/Tafsir source-policy decisions into one explicit policy path and surface those decisions truthfully in API responses.

## What this bundle changes
- Introduces `domains/policies/ask_source_policy.py` as the bounded Ask-source control plane.
- Makes `build_ask_plan()` consume a single policy decision instead of mixing request-intent, source selection, and composition rules inline.
- Surfaces `source_policy` in explain/ask responses so callers can see:
  - whether Quran was selected
  - whether Tafsir was requested
  - whether Tafsir was included or suppressed
  - what policy reason won
- Changes `tafsir_source_id` request defaults to `null` / omitted so the system can distinguish governed default selection from an explicit caller override.

## Files to replace/add
- `domains/policies/ask_source_policy.py` (new)
- `domains/ask/planner_types.py`
- `domains/ask/planner.py`
- `domains/ask/dispatcher.py`
- `domains/ask/workflows/explain_answer.py`
- `domains/answer_engine/contracts.py`
- `domains/answer_engine/response_builder.py`
- `domains/ask/response_surface.py`
- `apps/ask_api/schemas.py`
- `tests/unit/test_answer_engine_planner.py`
- `tests/unit/test_ask_source_policy.py` (new)
- `tests/integration/test_explain_answer_source_policy_surface.py` (new)

## Validation
Run:
```bash
pytest
python -m pipelines.evaluation.run_quran_tafsir_acceptance
alembic upgrade head
```

## Manual checks
### 1) Governed default Tafsir selection
```json
{
  "query": "Tafsir of Surah Ikhlas",
  "include_tafsir": true
}
```
Expect `source_policy.tafsir.selected_source_id == "tafsir:ibn-kathir-en"` and `policy_reason == "selected"`.

### 2) Explicit suppression beats query wording
```json
{
  "query": "Tafsir of Surah Ikhlas",
  "include_tafsir": false
}
```
Expect `source_policy.tafsir.request_origin == "explicit_suppression"` and `included == false`.

### 3) Omitted `tafsir_source_id` uses governed default
```json
{
  "query": "Explain Surah Al-Rahman",
  "include_tafsir": true
}
```
Expect successful Tafsir-backed answer without having to send a source id.
