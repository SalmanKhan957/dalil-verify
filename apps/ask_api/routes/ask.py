from __future__ import annotations

from fastapi import APIRouter, Request

from apps.ask_api.schemas import AskRequest, AskResponse
from services.ask_workflows.dispatch import dispatch_ask_query

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
def ask(payload: AskRequest, request: Request) -> AskResponse:
    result = dispatch_ask_query(payload.query, request=request, debug=payload.debug)
    return AskResponse(**result)
