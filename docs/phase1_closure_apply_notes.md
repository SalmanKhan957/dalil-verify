# Phase 1 Closure Apply Notes

1. Replace/add the files in this bundle at the same repo-relative paths.
2. Delete `scripts/common/quran_match_collections_previous.py` after copying.
3. Run:

   ```bash
   pytest
   python -m pipelines.evaluation.run_quran_tafsir_acceptance
   alembic upgrade head
   ```

This tranche keeps `services/*` as compatibility shims but removes runtime-layer
imports from `scripts/*` across `apps/`, `domains/`, and `pipelines/`.
