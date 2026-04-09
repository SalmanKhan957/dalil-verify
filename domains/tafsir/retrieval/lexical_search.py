from __future__ import annotations

from domains.tafsir.repositories.lexical_search_repository import SqlAlchemyTafsirLexicalSearchRepository
from domains.tafsir.types import TafsirLexicalHit, TafsirLexicalQuery
from infrastructure.db.session import get_session


class TafsirLexicalSearchService:
    def __init__(self, *, database_url: str | None = None) -> None:
        self.database_url = database_url

    def search(self, query: TafsirLexicalQuery) -> list[TafsirLexicalHit]:
        with get_session(database_url=self.database_url) as session:
            repository = SqlAlchemyTafsirLexicalSearchRepository(session)
            return repository.search(query)
