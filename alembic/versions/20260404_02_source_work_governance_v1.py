from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260404_02"
down_revision = "20260404_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_works",
        sa.Column("default_for_explain", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "source_works",
        sa.Column("supports_quran_composition", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "source_works",
        sa.Column("priority_rank", sa.Integer(), nullable=False, server_default="1000"),
    )
    op.add_column("source_works", sa.Column("policy_note", sa.Text(), nullable=True))

    op.create_index(
        "idx_source_works_governance_selection",
        "source_works",
        ["source_domain", "enabled", "approved_for_answering", "default_for_explain", "priority_rank"],
    )

    op.execute(
        """
        UPDATE source_works
        SET supports_quran_composition = CASE
            WHEN source_domain = 'tafsir' AND source_kind = 'commentary' THEN true
            ELSE false
        END,
            default_for_explain = CASE
            WHEN source_id = 'tafsir:ibn-kathir-en' THEN true
            ELSE false
        END,
            priority_rank = CASE
            WHEN source_id = 'tafsir:ibn-kathir-en' THEN 10
            ELSE priority_rank
        END,
            policy_note = CASE
            WHEN source_id = 'tafsir:ibn-kathir-en' THEN 'Approved bounded Tafsir source for Quran span explanation and commentary-backed answer composition.'
            ELSE policy_note
        END
        """
    )


def downgrade() -> None:
    op.drop_index("idx_source_works_governance_selection", table_name="source_works")
    op.drop_column("source_works", "policy_note")
    op.drop_column("source_works", "priority_rank")
    op.drop_column("source_works", "supports_quran_composition")
    op.drop_column("source_works", "default_for_explain")
