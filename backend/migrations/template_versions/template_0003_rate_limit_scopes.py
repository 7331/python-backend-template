from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "template_0003"
down_revision: str | None = "template_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_scopes",
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("theoretical_arrival_microseconds", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("scope"),
        prefixes=["UNLOGGED"],
    )


def downgrade() -> None:
    raise RuntimeError("forward only: fix forward with a new revision")
