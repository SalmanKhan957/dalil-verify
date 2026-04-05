# Answer Surface Cleanup — Corrected Fix Apply Notes

Apply this bundle **on top of** the current repo state that already includes:
- Ask-surface convergence
- placeholder hardening
- Tafsir flag precedence
- governance control-plane hardening
- answer-surface cleanup
- the first answer-surface cleanup fix attempt

## Purpose

This is a **surgical compatibility correction**. It restores the public route seams and request plumbing that the prior cleanup fix regressed, while preserving the good part of that fix:
- Quran source origin truth is still computed from **raw request presence**
- origin semantics stay in **`source_policy.quran`**
- legacy **`quran_source_selection`** remains stable

## Files to replace

- `apps/ask_api/routes/ask.py`
- `apps/ask_api/routes/explain.py`
- `domains/ask/dispatcher.py`

## What this restores

### 1. Ask/Explain convergence stays intact
`/ask/explain` goes back to being a compatibility alias over the shared Ask dispatch surface.

### 2. Route-module monkeypatch seams stay available
`apps.ask_api.routes.explain` again exposes both:
- `dispatch_ask_query`
- `explain_answer`

That preserves the existing integration-contract tests and any route-level monkeypatching expectations.

### 3. Legacy dispatch kwargs flow is restored
`/ask` and `/ask/explain` both forward:
- `include_tafsir`
- `tafsir_source_id`
- `tafsir_limit`
- `quran_text_source_id`
- `quran_translation_source_id`
- `debug`

plus the new internal intent booleans:
- `quran_text_source_requested`
- `quran_translation_source_requested`

### 4. Explicit Tafsir suppression survives the `/ask` path
`include_tafsir=false` is again preserved through route -> dispatch -> planner/policy evaluation.

## Validation

Run:

```bash
pytest
python -m pipelines.evaluation.run_quran_tafsir_acceptance
alembic upgrade head
```

## Expected fixes

The following previously failing tests should return green after applying this bundle:

- `tests/integration/test_ask_explain_contract_alignment.py`
- `tests/integration/test_ask_surface_request_convergence.py`
- `tests/integration/test_explain_answer_source_policy_surface.py`

## Design note

This fix intentionally does **not** touch the planner/policy origin model again. That part of the last fix was directionally correct. The regression happened at the **route and dispatch compatibility layer**, so that is the only layer corrected here.
