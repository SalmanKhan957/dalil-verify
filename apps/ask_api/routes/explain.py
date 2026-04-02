from __future__ import annotations

from fastapi import APIRouter

from apps.ask_api.schemas import ExplainQuranReferenceRequest, ExplainQuranReferenceResponse
from services.ask_workflows.explain_quran_reference import explain_quran_reference

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("/explain", response_model=ExplainQuranReferenceResponse)
def explain_reference(payload: ExplainQuranReferenceRequest) -> ExplainQuranReferenceResponse:
    result = explain_quran_reference(payload.query)
    return ExplainQuranReferenceResponse(**result)
