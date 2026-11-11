from collections.abc import Sequence

revision: str = "app_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("app",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise RuntimeError("forward only: fix forward with a new revision")
