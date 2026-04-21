from __future__ import annotations

from domains.hadith.contracts import HadithLexicalHit
from domains.hadith_topical.contracts import (
    HadithTopicalCandidateGenerationRequest,
    HadithTopicalQuery,
    HadithTopicalResult,
)
from domains.hadith_topical.evidence_bundle import build_llm_composition_contract, build_topical_evidence_bundle
from domains.hadith_topical.evidence_gate import gate_topical_result
from domains.hadith_topical.guidance_unit_retriever import HadithGuidanceUnitRetriever
from domains.hadith_topical.query_family_classifier import classify_hadith_topic_family
from domains.hadith_topical.query_normalizer import normalize_hadith_topical_query
from domains.hadith_topical.reranker import NoOpHadithTopicalReranker
from domains.hadith_topical.result_selector import select_topical_candidates
from domains.hadith_topical.thematic_passage_retriever import HadithThematicPassageRetriever


# ---------------------------------------------------------------------------
# Bukhari detection helper
# ---------------------------------------------------------------------------

def _is_bukhari_collection(collection_source_id: str | None) -> bool:
    """Return True when the request targets the Sahih al-Bukhari corpus.

    Guidance units and thematic passages were built against the old enriched
    index schema.  They do not carry Bukhari hadith_id refs and would produce
    zero useful candidates for Bukhari queries, so both retrieval branches are
    skipped when Bukhari is detected.
    """
    return bool(collection_source_id and 'bukhari' in str(collection_source_id).lower())


# ---------------------------------------------------------------------------
# Lexical context merging (unchanged from original)
# ---------------------------------------------------------------------------

def _merge_candidate_with_lexical_context(candidate, lexical_hits: list[HadithLexicalHit] | None, query: HadithTopicalQuery):
    if not lexical_hits:
        return candidate
    lexical_by_ref = {hit.entry.canonical_ref_collection: hit for hit in lexical_hits if getattr(hit, 'entry', None) is not None}
    hit = lexical_by_ref.get(candidate.canonical_ref)
    if hit is None:
        return candidate
    metadata = dict(candidate.metadata or {})
    if metadata.get('guidance_unit_id') or metadata.get('thematic_passage'):
        metadata.setdefault('source_row_text', getattr(getattr(hit, 'entry', None), 'english_text', None))
        metadata.setdefault('english_narrator', getattr(getattr(hit, 'entry', None), 'english_narrator', None))
        return type(candidate)(
            canonical_ref=candidate.canonical_ref,
            source_id=candidate.source_id,
            retrieval_origin=candidate.retrieval_origin,
            lexical_score=candidate.lexical_score,
            vector_score=candidate.vector_score,
            fusion_score=candidate.fusion_score,
            rerank_score=candidate.rerank_score,
            central_topic_score=candidate.central_topic_score,
            answerability_score=candidate.answerability_score,
            narrative_specificity_score=candidate.narrative_specificity_score,
            incidental_topic_penalty=candidate.incidental_topic_penalty,
            guidance_role=candidate.guidance_role,
            topic_family=candidate.topic_family,
            matched_topics=candidate.matched_topics,
            matched_terms=candidate.matched_terms,
            metadata=metadata,
        )
    lexical_score = candidate.lexical_score
    if lexical_score is None:
        lexical_score = float(hit.rank_score if getattr(hit, 'rank_score', None) is not None else (getattr(hit, 'score', 0.0) or 0.0))
    fusion_score = candidate.fusion_score if candidate.fusion_score is not None else lexical_score
    matched_terms = tuple(candidate.matched_terms or ())
    if not matched_terms:
        matched_terms = tuple(hit.matched_terms or ())
    matched_topics = tuple(candidate.matched_topics or ())
    if not matched_topics:
        lowered_terms = {str(term).strip().lower() for term in matched_terms}
        matched_topics = tuple(topic for topic in query.topic_candidates if str(topic).strip().lower() in lowered_terms)
    metadata = dict(candidate.metadata or {})
    metadata.setdefault('snippet', getattr(hit, 'snippet', None))
    metadata.setdefault('english_text', getattr(getattr(hit, 'entry', None), 'english_text', None))
    metadata.setdefault('english_narrator', getattr(getattr(hit, 'entry', None), 'english_narrator', None))
    return type(candidate)(
        canonical_ref=candidate.canonical_ref,
        source_id=candidate.source_id,
        retrieval_origin=candidate.retrieval_origin,
        lexical_score=lexical_score,
        vector_score=candidate.vector_score,
        fusion_score=fusion_score,
        rerank_score=candidate.rerank_score,
        central_topic_score=candidate.central_topic_score,
        answerability_score=candidate.answerability_score,
        narrative_specificity_score=candidate.narrative_specificity_score,
        incidental_topic_penalty=candidate.incidental_topic_penalty,
        guidance_role=candidate.guidance_role,
        topic_family=candidate.topic_family,
        matched_topics=matched_topics,
        matched_terms=matched_terms,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Search service
# ---------------------------------------------------------------------------

class HadithTopicalSearchService:
    """Runtime search façade for family-aware topical hadith retrieval.

    For Bukhari queries:
        - Delegates entirely to HadithTopicalCandidateGenerator._generate_bukhari
        - Skips guidance_unit_retriever (built on old enriched schema, incompatible)
        - Skips thematic_passage_retriever (same reason)
        - Skips lexical_hits merging (Bukhari refs are hadith_ids, not collection refs)

    For all other collections:
        - Behaviour is unchanged from the pre-Bukhari implementation.
    """

    def __init__(
        self,
        *,
        database_url: str | None = None,
        reranker: NoOpHadithTopicalReranker | None = None,
        candidate_generator=None,
        guidance_unit_retriever: HadithGuidanceUnitRetriever | None = None,
        thematic_passage_retriever: HadithThematicPassageRetriever | None = None,
    ) -> None:
        self.database_url = database_url
        self.reranker = reranker or NoOpHadithTopicalReranker()
        self.candidate_generator = candidate_generator
        self.guidance_unit_retriever = (
            guidance_unit_retriever
            if guidance_unit_retriever is not None
            else (None if candidate_generator is not None else HadithGuidanceUnitRetriever())
        )
        self.thematic_passage_retriever = thematic_passage_retriever or HadithThematicPassageRetriever(database_url=database_url)

    def normalize(self, raw_query: str, *, language_hint: str | None = None) -> HadithTopicalQuery:
        return normalize_hadith_topical_query(raw_query, language_hint=language_hint)

    def select(self, query: HadithTopicalQuery, candidates):
        reranked = self.reranker.rerank(query, list(candidates))
        selected = select_topical_candidates(query, reranked)
        return gate_topical_result(query, selected)

    def _candidate_generator(self):
        if self.candidate_generator is None:
            from domains.hadith_topical.candidate_generation import HadithTopicalCandidateGenerator
            self.candidate_generator = HadithTopicalCandidateGenerator(database_url=self.database_url)
        return self.candidate_generator

    def search(
        self,
        *,
        raw_query: str,
        collection_source_id: str | None = None,
        limit: int = 5,
        lexical_hits: list[HadithLexicalHit] | None = None,
        language_hint: str | None = None,
    ) -> HadithTopicalResult:
        query = self.normalize(raw_query, language_hint=language_hint)
        family_decision = classify_hadith_topic_family(query)
        query.debug['retrieval_family'] = family_decision.family_id
        query.debug['family_decision'] = {
            'family_id': family_decision.family_id,
            'retrieval_strategy': family_decision.retrieval_strategy,
            'confidence': family_decision.confidence,
            'matched_aliases': list(family_decision.matched_aliases),
            'entity_slug': family_decision.entity_slug,
            'allow_generic_fallback': family_decision.allow_generic_fallback,
        }

        is_bukhari = _is_bukhari_collection(collection_source_id)
        candidate_pool_limit = max(limit * 6, 24)

        # Initialise debug accumulators
        guidance_debug: dict = {'artifact_candidate_count': 0, 'candidate_count': 0}
        thematic_debug: dict = {'candidate_count': 0}
        generation_debug: dict = {'candidate_count': 0, 'lexical_candidate_count': len(lexical_hits or [])}
        generation_warnings: tuple[str, ...] = ()
        enriched_candidates = []

        # ---------------------------------------------------------------
        # Bukhari path — hybrid retrieval, no guidance/thematic layers
        # ---------------------------------------------------------------
        if is_bukhari:
            generation = self._candidate_generator().generate(
                HadithTopicalCandidateGenerationRequest(
                    query=query,
                    collection_source_id=collection_source_id,
                    candidate_limit=candidate_pool_limit,
                    lexical_limit=max(limit * 6, 24),
                ),
                lexical_hits=None,   # Bukhari path does not use lexical DB hits
            )
            enriched_candidates = list(generation.candidates)
            generation_debug = generation.debug
            generation_warnings = generation.warnings

        # ---------------------------------------------------------------
        # Existing path — thematic passages or enriched index
        # ---------------------------------------------------------------
        elif family_decision.retrieval_strategy == 'thematic_passages':
            thematic_candidates, thematic_debug = self.thematic_passage_retriever.retrieve(
                query=query,
                family_decision=family_decision,
                collection_source_id=collection_source_id,
                lexical_hits=lexical_hits,
                limit=candidate_pool_limit,
            )
            enriched_candidates = list(thematic_candidates)
        else:
            generation = self._candidate_generator().generate(
                HadithTopicalCandidateGenerationRequest(
                    query=query,
                    collection_source_id=collection_source_id,
                    candidate_limit=candidate_pool_limit,
                    lexical_limit=max(limit * 6, 24),
                ),
                lexical_hits=lexical_hits,
            )
            guidance_candidates = []
            if self.guidance_unit_retriever is not None:
                guidance_candidates, guidance_debug = self.guidance_unit_retriever.retrieve(
                    query=query,
                    collection_source_id=collection_source_id,
                    limit=candidate_pool_limit,
                )
            enriched_candidates = [
                _merge_candidate_with_lexical_context(candidate, lexical_hits, query)
                for candidate in generation.candidates
            ]
            if guidance_candidates:
                enriched_candidates = list(guidance_candidates) + enriched_candidates
            generation_debug = generation.debug
            generation_warnings = generation.warnings

        # ---------------------------------------------------------------
        # Shared: select → gate → hydrate → build evidence bundle
        # ---------------------------------------------------------------
        result = self.select(query, list(enriched_candidates))

        hydrated_entries = {}
        hydration_error = None
        try:
            from domains.hadith_topical.hydrator import hydrate_hadith_entries_by_collection_refs
            hydrated_entries = hydrate_hadith_entries_by_collection_refs(
                [candidate.canonical_ref for candidate in result.selected],
                collection_source_id=collection_source_id,
                database_url=self.database_url,
            )
        except Exception as exc:
            hydration_error = str(exc)

        evidence_bundle = (
            build_topical_evidence_bundle(query, list(result.selected), max_items=min(max(limit, 3), 8))
            if result.selected
            else None
        )
        llm_contract = build_llm_composition_contract(evidence_bundle) if evidence_bundle else None

        result.debug.update(
            {
                'normalized_query': query.normalized_query,
                'topic_candidates': list(query.topic_candidates),
                'query_profile': query.query_profile,
                'retrieval_family': family_decision.family_id,
                'retrieval_strategy': family_decision.retrieval_strategy,
                'allow_generic_fallback': family_decision.allow_generic_fallback,
                'family_decision': query.debug.get('family_decision'),
                'is_bukhari_path': is_bukhari,
                'candidate_generation': generation_debug,
                'guidance_unit_retrieval': guidance_debug,
                'thematic_passage_retrieval': thematic_debug,
                'candidate_pool_size': len(enriched_candidates),
                'selected_refs': [candidate.canonical_ref for candidate in result.selected],
                'selected_guidance_unit_ids': [
                    str((candidate.metadata or {}).get('guidance_unit_id') or '')
                    for candidate in result.selected
                    if (candidate.metadata or {}).get('guidance_unit_id')
                ],
                'selected_thematic_passages': [
                    str(candidate.canonical_ref)
                    for candidate in result.selected
                    if (candidate.metadata or {}).get('thematic_passage')
                ],
                'hydrated_refs': list(hydrated_entries.keys()),
                'selected_entries_found': len(hydrated_entries),
                'hydration_error': hydration_error,
                'evidence_bundle': evidence_bundle,
                'llm_composition_contract': llm_contract,
            }
        )

        combined_warnings = [*result.warnings, *generation_warnings]

        if is_bukhari:
            retrieval_origin = (generation_debug or {}).get('retrieval_origin', 'bukhari_hybrid')
            combined_warnings.append(f'bukhari_hybrid_retrieval:{retrieval_origin}')
        elif family_decision.retrieval_strategy == 'thematic_passages':
            combined_warnings.append('hadith_topic_family_thematic_passage_selected')
            if not enriched_candidates:
                combined_warnings.append('no_family_aligned_thematic_passages')
        elif result.selected and any(
            (candidate.metadata or {}).get('guidance_unit_id') for candidate in result.selected
        ):
            combined_warnings.append('guidance_unit_candidates_available')

        result.warnings = tuple(dict.fromkeys(combined_warnings))
        return result
