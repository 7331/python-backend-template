from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.models import Base


class RateLimitScope(Base):
    __tablename__ = "rate_limit_scopes"
    __table_args__ = ({"prefixes": ["UNLOGGED"]},)

    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    theoretical_arrival_microseconds: Mapped[int] = mapped_column(BigInteger)
