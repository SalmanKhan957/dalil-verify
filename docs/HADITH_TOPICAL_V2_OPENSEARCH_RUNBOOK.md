# Hadith Topical v2 — OpenSearch Runbook

## What this tranche does
- builds enriched Hadith topical documents
- indexes them into OpenSearch using BM25 fields and centrality metadata
- keeps the public Ask runtime on the bounded v1 lane
- runs Hadith Topical v2 in shadow mode for diagnostics and evaluation

## When to use OpenSearch
Use OpenSearch **now** for lexical candidate generation. Do **not** wait for embeddings.

Sequence:
1. OpenSearch BM25 lexical retrieval
2. Embeddings + vector retrieval
3. Hybrid fusion + reranking
4. Public v1 → v2 swap only after judged evals improve

## Local OpenSearch boot (Docker)
PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev\start_opensearch_local.ps1
```

Bash:

```bash
bash ./scripts/dev/start_opensearch_local.sh
```

## Environment variables
PowerShell:

```powershell
$env:OPENSEARCH_URL = "http://localhost:9200"
$env:OPENSEARCH_USERNAME = "admin"
$env:OPENSEARCH_PASSWORD = "admin"
$env:OPENSEARCH_VERIFY_SSL = "false"
```

## Build topical documents
```powershell
python -m scripts.dev.run_hadith_topical_build --input .\tmp\hadith_records.json --output .\tmp\hadith_topical_documents.json
```

Input is expected to be a JSON list of canonical Hadith records.

## Push topical documents to OpenSearch
```powershell
python -m scripts.dev.run_hadith_topical_push --documents .\tmp\hadith_topical_documents.json
```

## Run targeted tests
```powershell
pytest tests/unit/test_hadith_topical_query_normalizer.py `
       tests/unit/test_hadith_topical_enricher_contracts.py `
       tests/unit/test_hadith_topical_result_selector.py `
       tests/unit/test_hadith_topical_search_service.py `
       tests/integration/test_hadith_topical_index_documents.py `
       tests/integration/test_hadith_topical_v2_shadow_flow.py -q
```

## Manual API verification
Run the normal public API:

```powershell
python -m scripts.dev.run_public_api
```

Then call `/ask` with debug enabled:

```json
{
  "query": "give hadith about anger",
  "debug": true
}
```

Expected:
- public response still comes from bounded v1 topical lane
- `debug.runtime_diagnostics.hadith.topical_v2_shadow` is present
- with OpenSearch configured, `opensearch_candidate_count` should be greater than 0 for indexed data
