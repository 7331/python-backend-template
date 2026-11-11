from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Identity, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def list_enum_values(enum_class: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]


def build_postgres_enum(enum_class: type[Enum], *, name: str) -> SqlEnum:
    return SqlEnum(enum_class, name=name, values_callable=list_enum_values)


class Base(DeclarativeBase):
    __abstract__ = True


class SurrogateId:
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
