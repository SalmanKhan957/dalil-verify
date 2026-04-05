"""create hadith canonical tables

Revision ID: 20260406_01
Revises: 20260405_01
Create Date: 2026-04-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260406_01"
down_revision = "20260405_01"
branch_labels = None
depends_on = None


def _json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "hadith_books",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_book_id", sa.Text(), nullable=False),
        sa.Column("book_number", sa.Integer(), nullable=False),
        sa.Column("upstream_book_id", sa.Integer(), nullable=False),
        sa.Column("title_en", sa.Text(), nullable=False),
        sa.Column("title_ar", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("canonical_book_id", name="hadith_books_canonical_book_id_unique"),
        sa.UniqueConstraint("work_id", "book_number", name="hadith_books_work_book_number_unique"),
        sa.UniqueConstraint("work_id", "upstream_book_id", name="hadith_books_work_upstream_book_id_unique"),
    )
    op.create_index("idx_hadith_books_work_number", "hadith_books", ["work_id", "book_number"])

    op.create_table(
        "hadith_chapters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("hadith_books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_chapter_id", sa.Text(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("upstream_chapter_id", sa.Integer(), nullable=False),
        sa.Column("title_en", sa.Text(), nullable=True),
        sa.Column("title_ar", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("canonical_chapter_id", name="hadith_chapters_canonical_chapter_id_unique"),
        sa.UniqueConstraint("work_id", "book_id", "chapter_number", name="hadith_chapters_work_book_chapter_number_unique"),
        sa.UniqueConstraint("work_id", "upstream_chapter_id", name="hadith_chapters_work_upstream_chapter_id_unique"),
    )
    op.create_index("idx_hadith_chapters_work_book_number", "hadith_chapters", ["work_id", "book_id", "chapter_number"])

    op.create_table(
        "hadith_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("hadith_books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("hadith_chapters.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("canonical_entry_id", sa.Text(), nullable=False),
        sa.Column("canonical_ref_collection", sa.Text(), nullable=False),
        sa.Column("canonical_ref_book_hadith", sa.Text(), nullable=True),
        sa.Column("canonical_ref_book_chapter_hadith", sa.Text(), nullable=True),
        sa.Column("collection_hadith_number", sa.Integer(), nullable=False),
        sa.Column("in_book_hadith_number", sa.Integer(), nullable=True),
        sa.Column("upstream_entry_id", sa.Integer(), nullable=False),
        sa.Column("upstream_book_id", sa.Integer(), nullable=False),
        sa.Column("upstream_chapter_id", sa.Integer(), nullable=True),
        sa.Column("english_narrator", sa.Text(), nullable=True),
        sa.Column("english_text", sa.Text(), nullable=True),
        sa.Column("arabic_text", sa.Text(), nullable=True),
        sa.Column("narrator_chain_text", sa.Text(), nullable=True),
        sa.Column("matn_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("raw_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("collection_hadith_number >= 1", name="hadith_entries_collection_number_check"),
        sa.CheckConstraint(
            "in_book_hadith_number IS NULL OR in_book_hadith_number >= 1",
            name="hadith_entries_in_book_number_check",
        ),
        sa.UniqueConstraint("canonical_entry_id", name="hadith_entries_canonical_entry_id_unique"),
        sa.UniqueConstraint("canonical_ref_collection", name="hadith_entries_canonical_ref_collection_unique"),
        sa.UniqueConstraint("work_id", "collection_hadith_number", name="hadith_entries_work_collection_number_unique"),
        sa.UniqueConstraint("work_id", "upstream_entry_id", name="hadith_entries_work_upstream_entry_id_unique"),
    )
    op.create_index("idx_hadith_entries_work_collection_number", "hadith_entries", ["work_id", "collection_hadith_number"])
    op.create_index("idx_hadith_entries_work_book_in_book", "hadith_entries", ["work_id", "book_id", "in_book_hadith_number"])
    op.create_index("idx_hadith_entries_work_chapter_in_book", "hadith_entries", ["work_id", "chapter_id", "in_book_hadith_number"])

    op.create_table(
        "hadith_gradings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("hadith_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grade_label", sa.Text(), nullable=False),
        sa.Column("grade_text", sa.Text(), nullable=True),
        sa.Column("grader_name", sa.Text(), nullable=False, server_default=sa.text("'collection_default'")),
        sa.Column("provenance_note", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("grade_label IN ('sahih', 'hasan', 'daif', 'unknown')", name="hadith_gradings_grade_label_check"),
        sa.UniqueConstraint("entry_id", "grader_name", name="hadith_gradings_entry_grader_unique"),
    )
    op.create_index("idx_hadith_gradings_entry", "hadith_gradings", ["entry_id"])

    op.create_table(
        "hadith_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("work_id", sa.Integer(), sa.ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_root", sa.Text(), nullable=False),
        sa.Column("upstream_provider", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("collections_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("books_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chapters_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entries_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gradings_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes_json", _json_type(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'completed_with_warnings', 'failed')",
            name="hadith_ingestion_runs_status_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("hadith_ingestion_runs")
    op.drop_index("idx_hadith_gradings_entry", table_name="hadith_gradings")
    op.drop_table("hadith_gradings")
    op.drop_index("idx_hadith_entries_work_chapter_in_book", table_name="hadith_entries")
    op.drop_index("idx_hadith_entries_work_book_in_book", table_name="hadith_entries")
    op.drop_index("idx_hadith_entries_work_collection_number", table_name="hadith_entries")
    op.drop_table("hadith_entries")
    op.drop_index("idx_hadith_chapters_work_book_number", table_name="hadith_chapters")
    op.drop_table("hadith_chapters")
    op.drop_index("idx_hadith_books_work_number", table_name="hadith_books")
    op.drop_table("hadith_books")
