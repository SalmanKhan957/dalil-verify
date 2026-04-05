from __future__ import annotations

from fastapi import APIRouter, Request

from apps.api.schemas import VerifyQuranRequest, VerifyQuranResponse
from apps.verifier_api.service import verify_quran_logic

router = APIRouter(tags=["verifier"])


@router.post("/verify/quran", response_model=VerifyQuranResponse)
def verify_quran(request: Request, payload: VerifyQuranRequest, debug: bool = False) -> VerifyQuranResponse:
    return verify_quran_logic(request=request, payload=payload, debug=debug)
