"""create quran canonical tables

Revision ID: 20260405_01
Revises: 20260404_03
Create Date: 2026-04-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260405_01"
down_revision = "20260404_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quran_surahs",
        sa.Column("surah_no", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("surah_name_ar", sa.String(length=255), nullable=False),
        sa.Column("surah_name_en", sa.String(length=255), nullable=False),
        sa.Column("ayah_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("surah_no"),
    )

    op.create_table(
        "quran_ayahs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_id", sa.Integer(), nullable=False),
        sa.Column("surah_no", sa.Integer(), nullable=False),
        sa.Column("ayah_no", sa.Integer(), nullable=False),
        sa.Column("canonical_source_id", sa.String(length=255), nullable=False),
        sa.Column("citation_string", sa.String(length=64), nullable=False),
        sa.Column("text_display", sa.Text(), nullable=False),
        sa.Column("text_normalized_light", sa.Text(), nullable=False),
        sa.Column("text_normalized_aggressive", sa.Text(), nullable=False),
        sa.Column("bismillah", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ayah_no >= 1", name="quran_ayahs_ayah_no_check"),
        sa.ForeignKeyConstraint(["surah_no"], ["quran_surahs.surah_no"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_id"], ["source_works.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_source_id", name="quran_ayahs_canonical_source_id_unique"),
        sa.UniqueConstraint("work_id", "surah_no", "ayah_no", name="quran_ayahs_work_surah_ayah_unique"),
    )
    op.create_index("idx_quran_ayahs_work_surah", "quran_ayahs", ["work_id", "surah_no"])
    op.create_index("idx_quran_ayahs_work_surah_ayah", "quran_ayahs", ["work_id", "surah_no", "ayah_no"])

    op.create_table(
        "quran_translation_ayahs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_id", sa.Integer(), nullable=False),
        sa.Column("surah_no", sa.Integer(), nullable=False),
        sa.Column("ayah_no", sa.Integer(), nullable=False),
        sa.Column("text_display", sa.Text(), nullable=False),
        sa.Column("text_raw_html", sa.Text(), nullable=True),
        sa.Column("translation_name", sa.String(length=255), nullable=True),
        sa.Column("translator", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ayah_no >= 1", name="quran_translation_ayahs_ayah_no_check"),
        sa.ForeignKeyConstraint(["surah_no"], ["quran_surahs.surah_no"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_id"], ["source_works.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_id",
            "surah_no",
            "ayah_no",
            name="quran_translation_ayahs_work_surah_ayah_unique",
        ),
    )
    op.create_index(
        "idx_quran_translation_ayahs_work_surah",
        "quran_translation_ayahs",
        ["work_id", "surah_no"],
    )
    op.create_index(
        "idx_quran_translation_ayahs_work_surah_ayah",
        "quran_translation_ayahs",
        ["work_id", "surah_no", "ayah_no"],
    )


def downgrade() -> None:
    op.drop_index("idx_quran_translation_ayahs_work_surah_ayah", table_name="quran_translation_ayahs")
    op.drop_index("idx_quran_translation_ayahs_work_surah", table_name="quran_translation_ayahs")
    op.drop_table("quran_translation_ayahs")

    op.drop_index("idx_quran_ayahs_work_surah_ayah", table_name="quran_ayahs")
    op.drop_index("idx_quran_ayahs_work_surah", table_name="quran_ayahs")
    op.drop_table("quran_ayahs")

    op.drop_table("quran_surahs")
