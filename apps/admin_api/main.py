from fastapi import FastAPI
from apps.admin_api.routes.source_works import router as source_works_router
from apps.admin_api.routes.ingestion_runs import router as ingestion_runs_router
from apps.admin_api.routes.governance import router as governance_router

app = FastAPI(title="Dalil Admin API", version="0.1.0", description="Admin API scaffold; not wired for production yet.")
app.include_router(source_works_router)
app.include_router(ingestion_runs_router)
app.include_router(governance_router)
