# Production Checks

This repo is still pre-production. Search, queue, cache, and admin surfaces are scaffolded only.

## Anchored follow-up deployment constraint

The current anchor store is **process-local**. In its default form it uses in-memory dictionaries and does **not** propagate across multiple Uvicorn/Gunicorn workers.

Until a shared backend such as Redis is enabled, deploy anchored follow-up with:
- **one application worker**
- no expectation of cross-worker/session persistence

If you deploy multiple workers without a shared anchor backend, anchored follow-up can fail silently because turns may hydrate on a different worker than the one that saved the anchors.
