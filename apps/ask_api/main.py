from __future__ import annotations

# Load .env BEFORE settings is first imported, so OPENAI_API_KEY etc. reach
# the runtime embedding client / query normalizer / renderer. Without this,
# kNN retrieval silently disables itself when the shell env lacks the key.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI

from apps.ask_api.routes.ask import router as ask_router
from apps.ask_api.routes.explain import router as explain_router
from apps.ask_api.routes.health import router as health_router
from domains.quran.verifier.bootstrap import lifespan

app = FastAPI(
    title="Dalil Ask API",
    version="0.4.0",
    description=(
        "Bounded Ask API for Quran reference explanation and Arabic quote routing. "
        "Loads the shared Quran runtime so ask lanes remain self-sufficient."
    ),
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(ask_router)
app.include_router(explain_router)
