from apps.verifier_api.service import build_health_payload
from fastapi import APIRouter

router = APIRouter(tags=['health'])


@router.get('/health')
def health() -> dict:
    payload = build_health_payload()
    payload['service'] = 'dalil-public-api'
    return payload
