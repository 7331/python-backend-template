from collections.abc import Sequence

from alembic import op

revision: str = "template_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("template",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")


def downgrade() -> None:
    raise RuntimeError("forward only: fix forward with a new revision")
