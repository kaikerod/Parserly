"""Add external user identities.

Revision ID: 20260522_0003
Revises: 20260507_0002
Create Date: 2026-05-22 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260522_0003"
down_revision: str | None = "20260507_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_user_identities_provider_subject",
        ),
    )
    op.create_index("idx_user_identities_user_id", "user_identities", ["user_id"])
    op.create_index(
        "idx_user_identities_provider_subject_lower",
        "user_identities",
        [sa.text("lower(provider)"), "provider_subject"],
    )
    op.create_index(
        "idx_user_identities_provider_email_lower",
        "user_identities",
        [sa.text("lower(provider)"), sa.text("lower(email)")],
    )


def downgrade() -> None:
    op.drop_index("idx_user_identities_provider_email_lower", table_name="user_identities")
    op.drop_index("idx_user_identities_provider_subject_lower", table_name="user_identities")
    op.drop_index("idx_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
