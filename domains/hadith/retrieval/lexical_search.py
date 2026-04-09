from __future__ import annotations

from domains.hadith.contracts import HadithLexicalHit, HadithLexicalQuery
from domains.hadith.repositories.lexical_search_repository import SqlAlchemyHadithLexicalSearchRepository
from infrastructure.db.session import get_session


class HadithLexicalSearchService:
    def __init__(self, *, database_url: str | None = None) -> None:
        self.database_url = database_url

    def search(self, query: HadithLexicalQuery) -> list[HadithLexicalHit]:
        with get_session(database_url=self.database_url) as session:
            repository = SqlAlchemyHadithLexicalSearchRepository(session)
            return repository.search(query)
