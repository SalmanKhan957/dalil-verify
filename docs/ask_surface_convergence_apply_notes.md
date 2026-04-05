# Ask-surface convergence tranche

This bundle makes `POST /ask` the richer canonical ask surface while keeping `POST /ask/explain` as a compatibility alias over the same dispatch path.

## Changes
- `AskRequest` now accepts `include_tafsir`, `tafsir_source_id`, and `tafsir_limit`.
- `dispatch_ask_query()` now accepts the same Tafsir controls used by explain-mode flows.
- `/ask/explain` now delegates to `dispatch_ask_query()` and then strips legacy-only envelope fields (`route`, `result`).
- Added convergence tests so the two endpoints continue to share one execution path.

## Intent
- Reduce drift between `/ask` and `/ask/explain`.
- Preserve backward compatibility.
- Prepare for later decision on whether `/ask/explain` should be deprecated or retained as a compatibility alias.
