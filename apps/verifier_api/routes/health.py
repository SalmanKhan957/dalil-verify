from apps.verifier_api.service import build_health_payload
from fastapi import APIRouter

router = APIRouter(tags=['health'])


@router.get('/health')
def health() -> dict:
    return build_health_payload()
