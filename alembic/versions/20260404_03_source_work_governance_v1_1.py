from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260404_03"
down_revision = "20260404_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_works
        SET
            enabled = true,
            approved_for_answering = true,
            default_for_explain = true,
            supports_quran_composition = true,
            priority_rank = 10,
            policy_note = COALESCE(
                policy_note,
                'Approved bounded Tafsir source for Quran span explanation and commentary-backed answer composition.'
            )
        WHERE source_id = 'tafsir:ibn-kathir-en'
        """
    )

    op.execute(
        """
        UPDATE source_works
        SET default_for_explain = false
        WHERE source_domain = 'tafsir'
          AND source_id <> 'tafsir:ibn-kathir-en'
          AND default_for_explain = true
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE source_works
        SET
            enabled = false,
            approved_for_answering = false
        WHERE source_id = 'tafsir:ibn-kathir-en'
        """
    )
