from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from infrastructure.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class SourceWorkORM(TimestampMixin, Base):
    __tablename__ = "source_works"
    __table_args__ = (
        CheckConstraint("source_domain IN ('quran', 'tafsir', 'hadith')", name="source_works_domain_check"),
        CheckConstraint(
            "source_kind IN ('canonical_text', 'translation', 'commentary', 'hadith_collection')",
            name="source_works_kind_check",
        ),
        UniqueConstraint("upstream_provider", "upstream_resource_id", name="source_works_provider_resource_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    work_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    citation_label: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    upstream_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    upstream_resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    approved_for_answering: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    default_for_explain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    supports_quran_composition: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1000, server_default="1000")
    version_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict, server_default="{}")
