from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from domains.tafsir.retrieval.scoring import score_tafsir_row
from domains.tafsir.types import TafsirLexicalHit, TafsirLexicalQuery
from infrastructure.db.models.source_work import SourceWorkORM
from infrastructure.db.models.tafsir_section import TafsirSectionORM
from shared.utils.lexical import build_snippet, expand_query_tokens, field_score, normalize_search_text, tokenize_search_text


class TafsirLexicalSearchRepository(Protocol):
    def search(self, query: TafsirLexicalQuery) -> list[TafsirLexicalHit]: ...


class SqlAlchemyTafsirLexicalSearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: TafsirLexicalQuery) -> list[TafsirLexicalHit]:
        normalized = normalize_search_text(query.topical_query)
        query_tokens = expand_query_tokens(tokenize_search_text(normalized))
        if not normalized or not query_tokens:
            return []

        candidate_rows = self._fetch_candidates(query, normalized)
        hits: list[TafsirLexicalHit] = []
        for row in candidate_rows:
            score, matched_terms = score_tafsir_row(row, normalized, query_tokens)
            if score <= 0:
                continue
            hits.append(
                TafsirLexicalHit(
                    section_id=row.section_id,
                    canonical_section_id=row.canonical_section_id,
                    work_id=row.work_id,
                    source_id=row.source_id,
                    display_name=row.display_name,
                    citation_label=row.citation_label,
                    surah_no=row.surah_no,
                    ayah_start=row.ayah_start,
                    ayah_end=row.ayah_end,
                    anchor_verse_key=row.anchor_verse_key,
                    quran_span_ref=row.quran_span_ref,
                    text_plain=row.text_plain,
                    text_html=row.text_html,
                    score=score,
                    matched_terms=matched_terms,
                    snippet=build_snippet(row.text_plain, query_text=normalized),
                    retrieval_method=row.retrieval_method,
                )
            )

        hits.sort(key=lambda item: (-item.score, item.surah_no, item.ayah_start, item.section_id))
        return hits[: max(1, int(query.limit or 5))]

    def _fetch_candidates(self, query: TafsirLexicalQuery, normalized_query: str):
        stmt = (
            select(
                TafsirSectionORM.id.label('section_id'),
                TafsirSectionORM.canonical_section_id,
                TafsirSectionORM.work_id,
                SourceWorkORM.source_id,
                SourceWorkORM.display_name,
                SourceWorkORM.citation_label,
                TafsirSectionORM.surah_no,
                TafsirSectionORM.ayah_start,
                TafsirSectionORM.ayah_end,
                TafsirSectionORM.anchor_verse_key,
                TafsirSectionORM.quran_span_ref,
                TafsirSectionORM.text_plain,
                TafsirSectionORM.text_html,
                literal('lexical_ranked_candidates').label('retrieval_method'),
            )
            .join(SourceWorkORM, SourceWorkORM.id == TafsirSectionORM.work_id)
            .where(SourceWorkORM.enabled.is_(True), SourceWorkORM.approved_for_answering.is_(True))
        )
        if query.source_id:
            stmt = stmt.where(SourceWorkORM.source_id == query.source_id)
        if query.surah_no is not None:
            stmt = stmt.where(TafsirSectionORM.surah_no == int(query.surah_no))

        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ''
        candidate_limit = max(int(query.limit or 5) * 10, 25)
        if dialect_name == 'postgresql':
            search_text = func.concat(
                func.coalesce(SourceWorkORM.display_name, ''),
                literal(' '),
                func.coalesce(SourceWorkORM.citation_label, ''),
                literal(' '),
                func.coalesce(TafsirSectionORM.quran_span_ref, ''),
                literal(' '),
                func.coalesce(TafsirSectionORM.anchor_verse_key, ''),
                literal(' '),
                func.coalesce(TafsirSectionORM.text_plain_normalized, ''),
            )
            vector = func.to_tsvector('simple', search_text)
            ts_query = func.websearch_to_tsquery('simple', normalized_query)
            rank = func.ts_rank_cd(vector, ts_query)
            stmt = stmt.add_columns(rank.label('rank_score')).where(vector.op('@@')(ts_query)).order_by(rank.desc())
            rows = self.session.execute(stmt.limit(candidate_limit)).all()
            return [_row_namespace(row._mapping, retrieval_method='postgres_fts_ranked') for row in rows]

        rows = self.session.execute(stmt).all()
        return [_row_namespace(row._mapping, retrieval_method='lexical_ranked_candidates') for row in rows]



def _row_namespace(mapping, *, retrieval_method: str | None = None) -> SimpleNamespace:
    payload = dict(mapping)
    if retrieval_method is not None:
        payload['retrieval_method'] = retrieval_method
    return SimpleNamespace(**payload)
