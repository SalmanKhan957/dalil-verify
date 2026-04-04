from __future__ import annotations

from fastapi import FastAPI

from apps.ask_api.routes.ask import router as ask_router
from apps.ask_api.routes.explain import router as ask_explain_router
from apps.verifier_api.routes.verify import router as verify_router
from services.quran_runtime.bootstrap import lifespan

app = FastAPI(
    title="Dalil Public API",
    version="0.7.0",
    description="Combined public API for verifier and ask lanes.",
    lifespan=lifespan,
)

app.include_router(verify_router)
app.include_router(ask_router)
app.include_router(ask_explain_router)
