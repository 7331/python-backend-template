from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "accounts_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("accounts",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("passkey_user_handle", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("username ~ '^[a-z0-9_]{3,32}$'", name="ck_accounts_username_format"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("passkey_user_handle"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "account_passkeys",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), nullable=False),
        sa.Column("transports", postgresql.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id"),
    )
    op.create_index(op.f("ix_account_passkeys_account_id"), "account_passkeys", ["account_id"], unique=False)
    op.create_table(
        "account_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("account_passkey_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_passkey_id"], ["account_passkeys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_account_sessions_account_passkey_id"), "account_sessions", ["account_passkey_id"], unique=False
    )
    op.create_index(op.f("ix_account_sessions_expires_at"), "account_sessions", ["expires_at"], unique=False)
    op.create_table(
        "passkey_challenges",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("challenge_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.Enum("sign_up", "sign_in", name="passkey_challenge_purpose"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sign_up_username", sa.String(length=32), nullable=True),
        sa.Column("sign_up_user_handle", sa.LargeBinary(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_hash"),
    )
    op.create_index(op.f("ix_passkey_challenges_expires_at"), "passkey_challenges", ["expires_at"], unique=False)


def downgrade() -> None:
    raise RuntimeError("forward only: fix forward with a new revision")
