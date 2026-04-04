# DALIL Phase 0-1 Execution Brief

## What was done in this pass

### 1. Ask runtime boundary fixed
`apps/ask_api/main.py` now uses the shared verifier lifespan so standalone Ask can handle Arabic Quran quote flows without a 500 runtime failure.

### 2. Runtime-boundary tests added
New integration tests now cover:
- standalone Ask explicit reference flow
- standalone Ask Arabic quote flow
- combined public API verifier + ask flow

### 3. Source contracts started
A minimal source registry and source schemas were added so DALIL can evolve toward source-governed answer planning instead of ad hoc source handling.

Files introduced:
- `shared/schemas/source_record.py`
- `shared/schemas/source_citation.py`
- `services/source_registry/registry.py`
- `services/source_registry/policies.py`

## What this does **not** do yet
- no Tafsir retrieval yet
- no Hadith domain yet
- no planner yet
- no conversation state yet
- no DB migration yet

## Recommended next coding phase
1. Move runtime-critical Quran utilities out of `scripts/` into an application package.
2. Introduce Tafsir source registry entries and a first Tafsir storage contract.
3. Build Tafsir overlap retrieval for already-resolved Quran spans.
4. Add an answer composer boundary before broadening Ask behavior.
