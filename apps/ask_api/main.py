from __future__ import annotations

from fastapi import FastAPI

from apps.ask_api.routes.explain import router as explain_router

app = FastAPI(
    title="Dalil Ask API",
    version="0.1.0",
    description="Bounded Ask API for explicit Quran reference explanation.",
)
app.include_router(explain_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "dalil-ask-api",
    }
