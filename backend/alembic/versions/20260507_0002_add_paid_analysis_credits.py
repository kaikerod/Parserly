"""Add paid analysis credits to users.

Revision ID: 20260507_0002
Revises: 20260503_0001
Create Date: 2026-05-07 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0002"
down_revision: str | None = "20260503_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "paid_analysis_credits",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE users
        SET
            paid_analysis_credits = GREATEST(-analyses_used, 0),
            analyses_used = GREATEST(analyses_used, 0)
        WHERE analyses_used < 0
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET analyses_used = analyses_used - paid_analysis_credits
        WHERE paid_analysis_credits > 0
        """
    )
    op.drop_column("users", "paid_analysis_credits")
