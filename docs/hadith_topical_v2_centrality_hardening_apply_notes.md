# Hadith Topical v2 — Centrality & OpenSearch Apply Notes

## Scope
This tranche hardens Hadith Topical v2 around:
- topic-centrality enrichment
- incidental-mention suppression
- OpenSearch BM25 candidate generation
- improved selector/evidence-gate logic
- local run helpers for document build and index push

## Public runtime status
- public Ask still remains on bounded topical Hadith v1
- Hadith Topical v2 still runs in shadow mode
- this tranche improves the shadow candidate pool and diagnostics

## File groups
### Core domain logic
- `domains/hadith_topical/contracts.py`
- `domains/hadith_topical/query_profile.py`
- `domains/hadith_topical/query_normalizer.py`
- `domains/hadith_topical/enricher.py`
- `domains/hadith_topical/candidate_generation.py`
- `domains/hadith_topical/result_selector.py`
- `domains/hadith_topical/evidence_gate.py`
- `domains/hadith_topical/search_service.py`

### Search / indexing
- `infrastructure/search/opensearch/hadith_topical_queries.py`
- `infrastructure/search/opensearch/hadith_topical_mapping.json`
- `pipelines/indexing/hadith/build_hadith_topical_documents.py`

### Dev run helpers
- `scripts/dev/run_hadith_topical_build.py`
- `scripts/dev/run_hadith_topical_push.py`
- `scripts/dev/start_opensearch_local.ps1`
- `scripts/dev/start_opensearch_local.sh`

### Documentation
- `docs/HADITH_TOPICAL_V2_OPENSEARCH_RUNBOOK.md`
- `docs/hadith_topical_v2_centrality_hardening_apply_notes.md`

### Tests
- `tests/unit/test_hadith_topical_query_normalizer.py`
- `tests/unit/test_hadith_topical_enricher_contracts.py`
- `tests/unit/test_hadith_topical_result_selector.py`
- `tests/unit/test_hadith_topical_search_service.py`
- `tests/integration/test_hadith_topical_index_documents.py`

## Validation run
```powershell
pytest tests/unit/test_hadith_topical_query_normalizer.py `
       tests/unit/test_hadith_topical_enricher_contracts.py `
       tests/unit/test_hadith_topical_result_selector.py `
       tests/unit/test_hadith_topical_search_service.py `
       tests/integration/test_hadith_topical_index_documents.py `
       tests/integration/test_hadith_topical_v2_shadow_flow.py -q
```
