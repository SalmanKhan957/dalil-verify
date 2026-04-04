from __future__ import annotations

from fastapi import Request

from apps.api.schemas import VerifyQuranRequest, VerifyQuranResponse
from services.quran_verifier.service import build_health_payload, verify_quran_text


def verify_quran_logic(request: Request, payload: VerifyQuranRequest, debug: bool = False) -> VerifyQuranResponse:
    client_ip = request.client.host if request.client else None
    return VerifyQuranResponse(**verify_quran_text(payload.text, debug=debug, client_ip=client_ip))
