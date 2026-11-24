from collections.abc import Sequence

from alembic import op

revision: str = "template_0002"
down_revision: str | None = "template_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'starterapp_application') THEN "
        "CREATE ROLE starterapp_application LOGIN; "
        "END IF; "
        "END $$"
    )
    op.execute("ALTER ROLE starterapp_application LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
    op.execute("GRANT CONNECT ON DATABASE starterapp TO starterapp_application")
    op.execute("GRANT USAGE ON SCHEMA public TO starterapp_application")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO starterapp_application")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO starterapp_application")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE starterapp IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO starterapp_application"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE starterapp IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO starterapp_application"
    )


def downgrade() -> None:
    raise RuntimeError("forward only: fix forward with a new revision")
