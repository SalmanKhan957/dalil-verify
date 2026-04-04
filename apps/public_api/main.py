from __future__ import annotations

from fastapi import FastAPI

from apps.public_api.routes.ask import router as ask_router
from apps.public_api.routes.explain import router as explain_router
from apps.public_api.routes.health import router as health_router
from apps.public_api.routes.verify_quran import router as verify_router
from services.quran_runtime.bootstrap import lifespan

app = FastAPI(
    title="Dalil Public API",
    version="0.8.0",
    description="Combined public API for verifier and ask lanes.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(verify_router)
app.include_router(ask_router)
app.include_router(explain_router)
