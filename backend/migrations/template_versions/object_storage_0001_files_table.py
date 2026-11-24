from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "object_storage_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("object_storage",)
depends_on: str | Sequence[str] | None = "accounts_0001"


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index(op.f("ix_files_account_id"), "files", ["account_id"], unique=False)


def downgrade() -> None:
    raise RuntimeError("forward only: fix forward with a new revision")
