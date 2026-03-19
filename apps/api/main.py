from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from apps.api.logging_utils import append_jsonl_log
from apps.api.schemas import VerifyQuranRequest, VerifyQuranResponse
from scripts.evaluation.compare_quran_ayah_vs_passage import build_fusion_output
from scripts.evaluation.quran_passage_verifier_baseline import (
    build_passage_result,
    compute_best_passage_matches,
    load_quran_passage_dataset,
)
from scripts.evaluation.quran_verifier_baseline import (
    build_result as build_ayah_result,
    compute_best_matches as compute_ayah_matches,
    load_quran_dataset,
)

app = FastAPI(
    title="Dalil Verify API",
    version="0.3.1",
    description="Citation-first Quran verification API for Dalil Verify with ayah/passage fusion.",
)

QURAN_DATA_PATH = Path("data/processed/quran/quran_arabic_canonical.csv")
QURAN_PASSAGE_DATA_PATH = Path("data/processed/quran_passages/quran_passage_windows_v1.csv")

QURAN_ROWS = []
QURAN_PASSAGE_ROWS = []


@app.on_event("startup")
def startup_event() -> None:
    global QURAN_ROWS, QURAN_PASSAGE_ROWS

    if not QURAN_DATA_PATH.exists():
        raise RuntimeError(
            f"Canonical Quran dataset not found at: {QURAN_DATA_PATH}. "
            f"Run the parser first: python -m scripts.ingestion.parse_quran_xml"
        )

    if not QURAN_PASSAGE_DATA_PATH.exists():
        raise RuntimeError(
            f"Quran passage dataset not found at: {QURAN_PASSAGE_DATA_PATH}. "
            f"Run passage generation first: python -m scripts.ingestion.generate_quran_passage_windows"
        )

    QURAN_ROWS = load_quran_dataset(QURAN_DATA_PATH)
    QURAN_PASSAGE_ROWS = load_quran_passage_dataset(QURAN_PASSAGE_DATA_PATH)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "dalil-verify-api",
        "quran_rows_loaded": len(QURAN_ROWS),
        "quran_passage_rows_loaded": len(QURAN_PASSAGE_ROWS),
    }


def compact_result_for_api(fusion_output: dict, debug: bool = False) -> dict:
    preferred_lane = fusion_output.get("preferred_lane", "none")
    preferred_result = fusion_output.get("preferred_result") or {}
    preferred_best = preferred_result.get("best_match")
    secondary_result = fusion_output.get("secondary_result") or {}
    secondary_best = secondary_result.get("best_match")

    response = {
        "query": fusion_output.get("query", ""),
        "preferred_lane": preferred_lane,
        "match_status": preferred_result.get("match_status", "Cannot assess"),
        "confidence": preferred_result.get("confidence", "low"),
        "boundary_note": preferred_result.get(
            "boundary_note",
            "Based only on the current indexed Quran sources."
        ),
        "best_match": preferred_best,
        "also_related": [],
        "debug": None,
    }

    seen_citations = set()

    if preferred_best and preferred_best.get("citation"):
        seen_citations.add(preferred_best["citation"])

    if secondary_best and secondary_best.get("citation") and secondary_best["citation"] not in seen_citations:
        response["also_related"].append(
            {
                "lane": "passage" if preferred_lane == "ayah" else "ayah",
                "citation": secondary_best.get("citation"),
                "canonical_source_id": secondary_best.get("canonical_source_id"),
                "text_display": secondary_best.get("text_display"),
                "score": secondary_best.get("score"),
            }
        )
        seen_citations.add(secondary_best["citation"])

    for alt in preferred_result.get("alternatives", []):
        citation = alt.get("citation")
        if citation and citation not in seen_citations:
            response["also_related"].append(alt)
            seen_citations.add(citation)

    response["also_related"] = response["also_related"][:3]

    if debug:
        response["debug"] = {
            "decision_rule": fusion_output.get("decision_rule"),
            "rationale": fusion_output.get("rationale"),
            "query_token_count": fusion_output.get("query_token_count"),
            "analytics": fusion_output.get("analytics"),
            "ayah_result": fusion_output.get("ayah_result"),
            "passage_result": fusion_output.get("passage_result"),
            "secondary_result": fusion_output.get("secondary_result"),
        }

    return response


@app.post("/verify/quran", response_model=VerifyQuranResponse)
def verify_quran(request: Request, payload: VerifyQuranRequest, debug: bool = False) -> VerifyQuranResponse:
    if not QURAN_ROWS:
        raise HTTPException(status_code=500, detail="Quran dataset is not loaded.")

    if not QURAN_PASSAGE_ROWS:
        raise HTTPException(status_code=500, detail="Quran passage dataset is not loaded.")

    query = payload.text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")

    ayah_candidates = compute_ayah_matches(query, QURAN_ROWS, top_k=5)
    passage_candidates = compute_best_passage_matches(query, QURAN_PASSAGE_ROWS, top_k=5)

    ayah_result = build_ayah_result(query, ayah_candidates)
    passage_result = build_passage_result(query, passage_candidates)

    fusion_output = build_fusion_output(
        query=query,
        ayah_result=ayah_result,
        passage_result=passage_result,
    )

    public_response = compact_result_for_api(fusion_output, debug=debug)

    request_id = str(uuid4())
    best_match = public_response.get("best_match") or {}
    also_related = public_response.get("also_related") or []
    analytics = fusion_output.get("analytics", {})

    append_jsonl_log(
        {
            "request_id": request_id,
            "service": "verify_quran",
            "client_ip": request.client.host if request.client else None,
            "query": query,
            "query_char_count": len(query),
            "query_token_count": fusion_output.get("query_token_count"),
            "preferred_lane": public_response.get("preferred_lane"),
            "decision_rule": fusion_output.get("decision_rule"),
            "rationale": fusion_output.get("rationale"),
            "match_status": public_response.get("match_status"),
            "confidence": public_response.get("confidence"),
            "preferred_citation": best_match.get("citation"),
            "preferred_canonical_source_id": best_match.get("canonical_source_id"),
            "related_citations": [r.get("citation") for r in also_related if r.get("citation")],
            "ayah_status": (fusion_output.get("ayah_result") or {}).get("match_status"),
            "ayah_confidence": (fusion_output.get("ayah_result") or {}).get("confidence"),
            "ayah_citation": analytics.get("ayah_citation"),
            "ayah_score": analytics.get("ayah_score"),
            "ayah_status_rank": analytics.get("ayah_status_rank"),
            "passage_status": (fusion_output.get("passage_result") or {}).get("match_status"),
            "passage_confidence": (fusion_output.get("passage_result") or {}).get("confidence"),
            "passage_citation": analytics.get("passage_citation"),
            "passage_score": analytics.get("passage_score"),
            "passage_status_rank": analytics.get("passage_status_rank"),
            "passage_window_size": analytics.get("passage_window_size"),
            "passage_spans_multiple": analytics.get("passage_spans_multiple"),
            "score_delta_passage_minus_ayah": analytics.get("score_delta_passage_minus_ayah"),
            "debug_enabled": debug,
        }
    )

    return VerifyQuranResponse(**public_response)