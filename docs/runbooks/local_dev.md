# Local Dev

Use `scripts/dev/run_public_api.py` to start the combined API during the rewrite window.

## Anchored follow-up backend

The default anchor store in this repo is **process-local memory**. It is fine for local single-process development, but it is not shared across multiple workers or restarts.

For deterministic local follow-up testing:
- run a **single API worker**
- keep the same process alive across turns
- do not assume anchors survive restart unless you have explicitly enabled a persistent backend
