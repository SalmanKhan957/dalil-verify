# DALIL Renderer Backend Runbook

## Supported backends
- `deterministic` (default)
- `openai`

## Environment variables
- `DALIL_RENDERER_BACKEND=deterministic|openai`
- `DALIL_RENDERER_MODEL=gpt-5.4-mini`
- `DALIL_RENDERER_TIMEOUT_SECONDS=20`
- `DALIL_RENDERER_MAX_OUTPUT_TOKENS=800`
- `DALIL_RENDERER_FOLLOWUPS_ENABLED=true`
- `DALIL_RENDERER_CHAT_STYLE_ENABLED=true`
- `DALIL_RENDERER_VERBOSITY_DEFAULT=standard`
- `OPENAI_API_KEY=...`

## Guardrails
The hosted renderer is downstream of DALIL-owned composition truth. It must not perform routing, source selection, policy decisions, or evidence expansion.

## Failure mode
If the OpenAI renderer call fails or returns invalid output, DALIL must fall back to the deterministic renderer automatically.
