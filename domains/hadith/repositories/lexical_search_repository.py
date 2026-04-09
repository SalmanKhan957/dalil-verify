from __future__ import annotations

from typing import Protocol

from types import SimpleNamespace

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from domains.hadith.contracts import HadithLexicalHit, HadithLexicalQuery
from domains.hadith.retrieval.scoring import score_hadith_row
from domains.hadith.repositories.hadith_repository import _to_entry_record
from infrastructure.db.models.hadith_book import HadithBookORM
from infrastructure.db.models.hadith_chapter import HadithChapterORM
from infrastructure.db.models.hadith_entry import HadithEntryORM
from infrastructure.db.models.hadith_grading import HadithGradingORM
from infrastructure.db.models.source_work import SourceWorkORM
from shared.utils.lexical import build_snippet, expand_query_tokens, field_score, normalize_search_text, tokenize_search_text


class HadithLexicalSearchRepository(Protocol):
    def search(self, query: HadithLexicalQuery) -> list[HadithLexicalHit]: ...


class SqlAlchemyHadithLexicalSearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: HadithLexicalQuery) -> list[HadithLexicalHit]:
        normalized = normalize_search_text(query.topical_query)
        query_tokens = expand_query_tokens(tokenize_search_text(normalized))
        if not normalized or not query_tokens:
            return []

        candidate_rows = self._fetch_candidates(query, normalized, query_tokens)
        hits: list[HadithLexicalHit] = []
        for row in candidate_rows:
            score, matched_terms = score_hadith_row(row, normalized, query_tokens)
            if score <= 0:
                continue
            entry = _to_entry_record(row, row.collection_source_id, row.book_number, row.chapter_number, row.grading_row)
            hits.append(
                HadithLexicalHit(
                    entry=entry,
                    display_name=row.display_name,
                    citation_label=row.citation_label,
                    book_title=row.book_title,
                    chapter_title=row.chapter_title,
                    score=score,
                    matched_terms=matched_terms,
                    snippet=build_snippet(' '.join(filter(None, [row.english_narrator, row.english_text, row.matn_text])), query_text=normalized),
                    retrieval_method=row.retrieval_method,
                    rank_score=float(getattr(row, 'rank_score', 0.0) or 0.0),
                )
            )

        hits.sort(key=lambda item: (-item.score, -float(item.rank_score or 0.0), item.entry.collection_hadith_number, item.entry.id))
        return hits[: max(1, int(query.limit or 5))]

    def _fetch_candidates(self, query: HadithLexicalQuery, normalized_query: str, expanded_query_tokens: list[str]):
        base_base_stmt = (
            select(
                HadithEntryORM,
                SourceWorkORM.display_name,
                SourceWorkORM.citation_label,
                SourceWorkORM.source_id.label('collection_source_id'),
                HadithBookORM.book_number,
                HadithBookORM.title_en.label('book_title'),
                HadithChapterORM.chapter_number,
                HadithChapterORM.title_en.label('chapter_title'),
                HadithGradingORM,
                literal('lexical_ranked_candidates').label('retrieval_method'),
            )
            .join(SourceWorkORM, SourceWorkORM.id == HadithEntryORM.work_id)
            .join(HadithBookORM, HadithBookORM.id == HadithEntryORM.book_id)
            .outerjoin(HadithChapterORM, HadithChapterORM.id == HadithEntryORM.chapter_id)
            .outerjoin(HadithGradingORM, HadithGradingORM.entry_id == HadithEntryORM.id)
            .where(SourceWorkORM.enabled.is_(True))
        )
        if query.collection_source_id:
            base_base_stmt = base_base_stmt.where(SourceWorkORM.source_id == query.collection_source_id)

        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ''
        candidate_limit = max(int(query.limit or 5) * 50, 200)
        if dialect_name == 'postgresql':
            search_text = func.concat(
                func.coalesce(SourceWorkORM.display_name, ''),
                literal(' '),
                func.coalesce(SourceWorkORM.citation_label, ''),
                literal(' '),
                func.coalesce(HadithBookORM.title_en, ''),
                literal(' '),
                func.coalesce(HadithChapterORM.title_en, ''),
                literal(' '),
                func.coalesce(HadithEntryORM.english_narrator, ''),
                literal(' '),
                func.coalesce(HadithEntryORM.english_text, ''),
                literal(' '),
                func.coalesce(HadithEntryORM.matn_text, ''),
            )
            vector = func.to_tsvector('simple', search_text)
            search_query_text = _build_postgres_search_query_text(normalized_query, expanded_query_tokens)
            ts_query = func.websearch_to_tsquery('simple', search_query_text)
            rank = func.ts_rank_cd(vector, ts_query)
            ranked_stmt = base_base_stmt.add_columns(rank.label('rank_score')).where(vector.op('@@')(ts_query)).order_by(rank.desc())
            rows = self.session.execute(ranked_stmt.limit(candidate_limit)).all()
            if rows:
                return [_coerce_row_mapping(row._mapping, retrieval_method='postgres_fts_ranked') for row in rows]

        fallback_rows = self.session.execute(base_base_stmt.limit(max(candidate_limit, 5000))).all()
        return [_coerce_row_mapping(row._mapping, retrieval_method='lexical_ranked_candidates') for row in fallback_rows]


def _coerce_row_mapping(mapping, *, retrieval_method: str | None = None):
    return SimpleNamespace(**{
        'id': mapping[HadithEntryORM].id,
        'work_id': mapping[HadithEntryORM].work_id,
        'book_id': mapping[HadithEntryORM].book_id,
        'chapter_id': mapping[HadithEntryORM].chapter_id,
        'canonical_entry_id': mapping[HadithEntryORM].canonical_entry_id,
        'canonical_ref_collection': mapping[HadithEntryORM].canonical_ref_collection,
        'canonical_ref_book_hadith': mapping[HadithEntryORM].canonical_ref_book_hadith,
        'canonical_ref_book_chapter_hadith': mapping[HadithEntryORM].canonical_ref_book_chapter_hadith,
        'collection_hadith_number': mapping[HadithEntryORM].collection_hadith_number,
        'in_book_hadith_number': mapping[HadithEntryORM].in_book_hadith_number,
        'english_narrator': mapping[HadithEntryORM].english_narrator,
        'english_text': mapping[HadithEntryORM].english_text,
        'arabic_text': mapping[HadithEntryORM].arabic_text,
        'narrator_chain_text': mapping[HadithEntryORM].narrator_chain_text,
        'matn_text': mapping[HadithEntryORM].matn_text,
        'metadata_json': dict(mapping[HadithEntryORM].metadata_json or {}),
        'raw_json': dict(mapping[HadithEntryORM].raw_json or {}),
        'display_name': mapping['display_name'],
        'citation_label': mapping['citation_label'],
        'collection_source_id': mapping['collection_source_id'],
        'book_number': mapping['book_number'],
        'book_title': mapping['book_title'],
        'chapter_number': mapping['chapter_number'],
        'chapter_title': mapping['chapter_title'],
        'grading_row': mapping.get(HadithGradingORM),
        'retrieval_method': retrieval_method or mapping['retrieval_method'],
        'rank_score': mapping.get('rank_score'),
    })




def _build_postgres_search_query_text(normalized_query: str, expanded_query_tokens: list[str]) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in [normalized_query, *expanded_query_tokens]:
        cleaned = normalize_search_text(token)
        if not cleaned or cleaned in seen:
            continue
        tokens.append(cleaned)
        seen.add(cleaned)
    if not tokens:
        return normalized_query
    if len(tokens) == 1:
        return tokens[0]
    return ' OR '.join(tokens)
