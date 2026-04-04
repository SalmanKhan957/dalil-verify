from __future__ import annotations

from fastapi import FastAPI

from apps.ask_api.routes.ask import router as ask_router
from apps.ask_api.routes.explain import router as explain_router
from services.quran_runtime.bootstrap import lifespan

app = FastAPI(
    title="Dalil Ask API",
    version="0.3.0",
    description=(
        "Bounded Ask API for Quran reference explanation and Arabic quote routing. "
        "Loads the shared Quran runtime so ask lanes remain self-sufficient."
    ),
    lifespan=lifespan,
)
app.include_router(ask_router)
app.include_router(explain_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "dalil-ask-api",
    }
