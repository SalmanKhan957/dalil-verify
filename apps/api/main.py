from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from apps.api.logging_utils import append_jsonl_log
from apps.api.schemas import VerifyQuranRequest, VerifyQuranResponse
from apps.api.translation_support import attach_english_translation, load_english_translation_map
from scripts.common.quran_span_index import QuranSurahSpanIndex
from scripts.common.retrieval_shortlist import QuranShortlistIndex
from scripts.common.text_normalization import normalize_arabic_light, tokenize
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

QURAN_DATA_PATH = Path("data/processed/quran/quran_arabic_canonical.csv")
QURAN_PASSAGE_DATA_PATH = Path("data/processed/quran_passages/quran_passage_windows_v1.csv")
QURAN_EN_TRANSLATION_PATH = Path("data/processed/quran_translations/quran_en_single_translation.csv")

QURAN_ROWS: list[dict] = []
QURAN_PASSAGE_ROWS: list[dict] = []
AYAH_SHORTLIST_INDEX: QuranShortlistIndex | None = None
PASSAGE_SHORTLIST_INDEX: QuranShortlistIndex | None = None
SURAH_SPAN_INDEX: QuranSurahSpanIndex | None = None
ENGLISH_TRANSLATION_MAP: dict[tuple[int, int], dict] = {}
ENGLISH_TRANSLATION_INFO: dict = {"loaded": False, "row_count": 0, "path": str(QURAN_EN_TRANSLATION_PATH)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global QURAN_ROWS, QURAN_PASSAGE_ROWS
    global AYAH_SHORTLIST_INDEX, PASSAGE_SHORTLIST_INDEX, SURAH_SPAN_INDEX
    global ENGLISH_TRANSLATION_MAP, ENGLISH_TRANSLATION_INFO

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
    AYAH_SHORTLIST_INDEX = QuranShortlistIndex(QURAN_ROWS)
    PASSAGE_SHORTLIST_INDEX = QuranShortlistIndex(QURAN_PASSAGE_ROWS)
    SURAH_SPAN_INDEX = QuranSurahSpanIndex(QURAN_ROWS)
    ENGLISH_TRANSLATION_MAP, ENGLISH_TRANSLATION_INFO = load_english_translation_map(QURAN_EN_TRANSLATION_PATH)

    yield


app = FastAPI(
    title="Dalil Verify API",
    version="0.5.0",
    description=(
        "Citation-first Quran verification API for Dalil Verify with shortlist retrieval, "
        "ayah/passage fusion, and same-surah long-passage span matching."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "dalil-verify-api",
        "quran_rows_loaded": len(QURAN_ROWS),
        "quran_passage_rows_loaded": len(QURAN_PASSAGE_ROWS),
        "ayah_shortlist_index_ready": AYAH_SHORTLIST_INDEX is not None,
        "passage_shortlist_index_ready": PASSAGE_SHORTLIST_INDEX is not None,
        "surah_span_index_ready": SURAH_SPAN_INDEX is not None,
        "english_translation_loaded": ENGLISH_TRANSLATION_INFO.get("loaded", False),
        "english_translation_rows_loaded": ENGLISH_TRANSLATION_INFO.get("row_count", 0),
    }


def _dedupe_candidates(candidates: list[dict], limit: int = 5) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        row = candidate.get("row") or {}
        key = row.get("canonical_source_id") or row.get("citation_string")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


def _sort_candidates(candidates: list[dict], limit: int = 5) -> list[dict]:
    ordered = sorted(
        candidates,
        key=lambda x: (
            x.get("score", 0.0),
            x.get("exact_normalized_light", 0.0),
            x.get("contains_query_in_text_light", 0.0),
            x.get("token_coverage", 0.0),
        ),
        reverse=True,
    )
    return _dedupe_candidates(ordered, limit=limit)


def _is_long_query(query: str) -> bool:
    query_tokens = tokenize(normalize_arabic_light(query))
    return len(query_tokens) >= 12


def _merge_passage_candidates(
    query: str,
    *,
    static_candidates: list[dict],
    ayah_candidates: list[dict],
) -> tuple[list[dict], dict]:
    if SURAH_SPAN_INDEX is None or not _is_long_query(query):
        return _sort_candidates(static_candidates, limit=5), {"engine": "static_window", "candidate_count": len(static_candidates[:5])}

    dynamic_candidates, dynamic_meta = SURAH_SPAN_INDEX.find_long_passage_candidates(
        query,
        ayah_seed_candidates=ayah_candidates,
        passage_seed_candidates=static_candidates,
        min_window_size=5,
        max_window_size=12,
        top_k=5,
    )

    if not dynamic_candidates:
        return _sort_candidates(static_candidates, limit=5), {"engine": "static_window", "candidate_count": len(static_candidates[:5])}

    merged = _sort_candidates(dynamic_candidates + static_candidates, limit=5)
    engine = dynamic_meta.get("engine") or "static_window"
    if engine == "surah_span_exact":
        engine = "surah_span_exact"
    elif engine == "dynamic_expand":
        engine = "dynamic_expand"
    else:
        engine = "static_window"

    return merged, {
        "engine": engine,
        "candidate_count": len(merged),
        "dynamic_candidate_count": len(dynamic_candidates),
        **dynamic_meta,
    }


def _should_include_related(preferred_result: dict, related_item: dict | None) -> bool:
    if not related_item:
        return False

    score = float(related_item.get("score") or 0.0)
    preferred_status = preferred_result.get("match_status")
    preferred_confidence = preferred_result.get("confidence")

    if preferred_status == "Exact match found" and preferred_confidence == "high":
        return score >= 40.0

    return score >= 15.0


def compact_result_for_api(
    fusion_output: dict,
    *,
    debug: bool = False,
    english_translation_map: dict[tuple[int, int], dict] | None = None,
) -> dict:
    preferred_lane = fusion_output.get("preferred_lane", "none")
    preferred_result = fusion_output.get("preferred_result") or {}
    preferred_best = preferred_result.get("best_match")
    secondary_result = fusion_output.get("secondary_result") or {}
    secondary_best = secondary_result.get("best_match")

    if preferred_best:
        preferred_best = attach_english_translation(preferred_best, english_translation_map or {})

    response = {
        "query": fusion_output.get("query", ""),
        "preferred_lane": preferred_lane,
        "match_status": preferred_result.get("match_status", "Cannot assess"),
        "confidence": preferred_result.get("confidence", "low"),
        "boundary_note": preferred_result.get(
            "boundary_note",
            "Based only on the current indexed Quran sources.",
        ),
        "best_match": preferred_best,
        "also_related": [],
        "debug": None,
    }

    seen_citations = set()

    if preferred_best and preferred_best.get("citation"):
        seen_citations.add(preferred_best["citation"])

    if secondary_best:
        secondary_best = attach_english_translation(secondary_best, english_translation_map or {})

    if (
        secondary_best
        and secondary_best.get("citation")
        and secondary_best["citation"] not in seen_citations
        and _should_include_related(preferred_result, secondary_best)
    ):
        response["also_related"].append(
            {
                "lane": "passage" if preferred_lane == "ayah" else "ayah",
                "citation": secondary_best.get("citation"),
                "canonical_source_id": secondary_best.get("canonical_source_id"),
                "text_display": secondary_best.get("text_display"),
                "english_translation": secondary_best.get("english_translation"),
                "score": secondary_best.get("score"),
            }
        )
        seen_citations.add(secondary_best["citation"])

    for alt in preferred_result.get("alternatives", []):
        citation = alt.get("citation")
        if (
            citation
            and citation not in seen_citations
            and _should_include_related(preferred_result, alt)
        ):
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
            "shortlist": fusion_output.get("shortlist"),
            "english_translation": ENGLISH_TRANSLATION_INFO,
        }

    return response


@app.post("/verify/quran", response_model=VerifyQuranResponse)
def verify_quran(request: Request, payload: VerifyQuranRequest, debug: bool = False) -> VerifyQuranResponse:
    if not QURAN_ROWS or AYAH_SHORTLIST_INDEX is None:
        raise HTTPException(status_code=500, detail="Quran dataset/index is not loaded.")

    if not QURAN_PASSAGE_ROWS or PASSAGE_SHORTLIST_INDEX is None:
        raise HTTPException(status_code=500, detail="Quran passage dataset/index is not loaded.")

    query = payload.text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")

    ayah_shortlist_rows, ayah_shortlist_meta = AYAH_SHORTLIST_INDEX.shortlist_rows(query, limit=250)
    passage_shortlist_rows, passage_shortlist_meta = PASSAGE_SHORTLIST_INDEX.shortlist_rows(query, limit=300)

    ayah_candidates = compute_ayah_matches(query, ayah_shortlist_rows, top_k=5)
    static_passage_candidates = compute_best_passage_matches(query, passage_shortlist_rows, top_k=5)
    passage_candidates, dynamic_passage_meta = _merge_passage_candidates(
        query,
        static_candidates=static_passage_candidates,
        ayah_candidates=ayah_candidates,
    )

    ayah_result = build_ayah_result(query, ayah_candidates)
    passage_result = build_passage_result(query, passage_candidates)
    if passage_result.get("best_match") and dynamic_passage_meta.get("engine") != "static_window":
        passage_result["best_match"]["retrieval_engine"] = dynamic_passage_meta.get("engine")
        for alt in passage_result.get("alternatives", []):
            alt.setdefault("retrieval_engine", dynamic_passage_meta.get("engine"))

    fusion_output = build_fusion_output(
        query=query,
        ayah_result=ayah_result,
        passage_result=passage_result,
    )
    fusion_output["shortlist"] = {
        "ayah": ayah_shortlist_meta,
        "passage": passage_shortlist_meta,
        "dynamic_passage": dynamic_passage_meta,
    }
    fusion_output.setdefault("analytics", {})["passage_retrieval_engine"] = (
        (passage_result.get("best_match") or {}).get("retrieval_engine") or dynamic_passage_meta.get("engine")
    )

    public_response = compact_result_for_api(
        fusion_output,
        debug=debug,
        english_translation_map=ENGLISH_TRANSLATION_MAP,
    )

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
            "preferred_has_english_translation": bool(best_match.get("english_translation")),
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
            "passage_retrieval_engine": analytics.get("passage_retrieval_engine"),
            "ayah_shortlist_strategy": ayah_shortlist_meta.get("strategy"),
            "ayah_shortlist_candidate_count": ayah_shortlist_meta.get("candidate_count"),
            "passage_shortlist_strategy": passage_shortlist_meta.get("strategy"),
            "passage_shortlist_candidate_count": passage_shortlist_meta.get("candidate_count"),
            "dynamic_passage_engine": dynamic_passage_meta.get("engine"),
            "dynamic_passage_candidate_count": dynamic_passage_meta.get("candidate_count"),
            "debug_enabled": debug,
        }
    )

    return VerifyQuranResponse(**public_response)
