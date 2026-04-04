from fastapi import APIRouter

router = APIRouter(prefix="/admin/ingestion-runs", tags=["admin"])


@router.get("")
def list_ingestion_runs() -> dict[str, object]:
    return {"implemented": False, "message": "Admin ingestion runs API is scaffolded only."}
