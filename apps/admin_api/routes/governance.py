from fastapi import APIRouter

router = APIRouter(prefix="/admin/governance", tags=["admin"])


@router.get("")
def governance_status() -> dict[str, object]:
    return {"implemented": False, "message": "Admin governance API is scaffolded only."}
