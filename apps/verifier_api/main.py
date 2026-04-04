from __future__ import annotations

from fastapi import FastAPI

from apps.verifier_api.routes.verify import router as verify_router
from services.quran_runtime.bootstrap import lifespan

app = FastAPI(
    title="Dalil Verifier API",
    version="0.6.0",
    description=(
        "Verifier-only API for Quran verification with shortlist retrieval, "
        "same-surah long-passage matching, English attachment, and dual simple/Uthmani routing."
    ),
    lifespan=lifespan,
)

app.include_router(verify_router)
