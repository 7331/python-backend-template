from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.models import Base, SurrogateId, Timestamps

FILE_PUBLIC_ID_LENGTH = 32
FILE_CONTENT_TYPE_MAXIMUM_LENGTH = 127


class File(SurrogateId, Timestamps, Base):
    __tablename__ = "files"

    public_id: Mapped[str] = mapped_column(String(FILE_PUBLIC_ID_LENGTH), unique=True)
    content_type: Mapped[str] = mapped_column(String(FILE_CONTENT_TYPE_MAXIMUM_LENGTH))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
