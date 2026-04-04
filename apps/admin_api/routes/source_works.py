from fastapi import APIRouter

router = APIRouter(prefix="/admin/source-works", tags=["admin"])


@router.get("")
def list_source_works() -> dict[str, object]:
    return {"implemented": False, "message": "Admin source works API is scaffolded only."}
