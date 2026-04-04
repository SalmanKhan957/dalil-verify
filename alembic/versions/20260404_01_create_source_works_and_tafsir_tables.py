from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260404_01"
down_revision = None
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "source_works",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_domain", sa.Text(), nullable=False),
        sa.Column("work_slug", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("citation_label", sa.Text(), nullable=False),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("language_code", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("upstream_provider", sa.Text(), nullable=False),
        sa.Column("upstream_resource_id", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approved_for_answering", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version_label", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source_domain IN ('quran', 'tafsir', 'hadith')", name="source_works_domain_check"),
        sa.CheckConstraint(
            "source_kind IN ('canonical_text', 'translation', 'commentary', 'hadith_collection')",
            name="source_works_kind_check",
        ),
        sa.UniqueConstraint("source_id", name="source_works_source_id_key"),
        sa.UniqueConstraint("upstream_provider", "upstream_resource_id", name="source_works_provider_resource_unique"),
    )
    op.create_index("idx_source_works_domain", "source_works", ["source_domain"])
    op.create_index("idx_source_works_enabled", "source_works", ["enabled", "approved_for_answering"])

    op.create_table(
        "tafsir_sections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_section_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("upstream_provider", sa.Text(), nullable=False),
        sa.Column("upstream_resource_id", sa.Integer(), nullable=False),
        sa.Column("upstream_entry_id", sa.BigInteger(), nullable=False),
        sa.Column("language_code", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("language_id", sa.Integer(), nullable=True),
        sa.Column("surah_no", sa.Integer(), nullable=False),
        sa.Column("ayah_start", sa.Integer(), nullable=False),
        sa.Column("ayah_end", sa.Integer(), nullable=False),
        sa.Column("anchor_verse_key", sa.Text(), nullable=False),
        sa.Column("quran_span_ref", sa.Text(), nullable=False),
        sa.Column("coverage_mode", sa.Text(), nullable=False),
        sa.Column("coverage_confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("text_html", sa.Text(), nullable=False),
        sa.Column("text_plain", sa.Text(), nullable=False),
        sa.Column("text_plain_normalized", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("source_file_path", sa.Text(), nullable=True),
        sa.Column("source_manifest_path", sa.Text(), nullable=True),
        sa.Column("raw_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("ayah_start >= 1 AND ayah_end >= ayah_start", name="tafsir_sections_ayah_bounds_check"),
        sa.CheckConstraint(
            "coverage_mode IN ('explicit_range', 'inferred_from_empty_followers', 'anchor_only')",
            name="tafsir_sections_coverage_mode_check",
        ),
        sa.UniqueConstraint("canonical_section_id", name="tafsir_sections_canonical_section_id_key"),
        sa.UniqueConstraint("work_id", "upstream_entry_id", name="tafsir_sections_work_upstream_entry_unique"),
    )
    op.create_index("idx_tafsir_sections_work_surah", "tafsir_sections", ["work_id", "surah_no"])
    op.create_index(
        "idx_tafsir_sections_work_surah_start_end",
        "tafsir_sections",
        ["work_id", "surah_no", "ayah_start", "ayah_end"],
    )
    op.create_index("idx_tafsir_sections_anchor", "tafsir_sections", ["work_id", "anchor_verse_key"])
    op.create_index("idx_tafsir_sections_span_ref", "tafsir_sections", ["work_id", "quran_span_ref"])
    op.execute(
        "CREATE INDEX idx_tafsir_sections_plain_search ON tafsir_sections USING GIN (to_tsvector('simple', text_plain_normalized))"
    )

    op.create_table(
        "tafsir_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("source_root", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("chapters_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_rows_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sections_built", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_warnings', 'failed')",
            name="tafsir_ingestion_runs_status_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("tafsir_ingestion_runs")
    op.execute("DROP INDEX IF EXISTS idx_tafsir_sections_plain_search")
    op.drop_index("idx_tafsir_sections_span_ref", table_name="tafsir_sections")
    op.drop_index("idx_tafsir_sections_anchor", table_name="tafsir_sections")
    op.drop_index("idx_tafsir_sections_work_surah_start_end", table_name="tafsir_sections")
    op.drop_index("idx_tafsir_sections_work_surah", table_name="tafsir_sections")
    op.drop_table("tafsir_sections")
    op.drop_index("idx_source_works_enabled", table_name="source_works")
    op.drop_index("idx_source_works_domain", table_name="source_works")
    op.drop_table("source_works")
