from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.starter.files.models import File


class FileRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def insert_file_unless_present(
        self, public_id: str, *, content_type: str, size_bytes: int, account_id: int
    ) -> File | None:
        return await self.session.scalar(
            insert(File)
            .values(
                public_id=public_id,
                content_type=content_type,
                size_bytes=size_bytes,
                account_id=account_id,
            )
            .on_conflict_do_nothing(index_elements=[File.public_id])
            .returning(File)
        )

    async def find_file(self, public_id: str, *, account_id: int) -> File | None:
        return await self.session.scalar(select(File).where(File.public_id == public_id, File.account_id == account_id))

    async def delete_file(self, public_id: str, *, account_id: int) -> int | None:
        return await self.session.scalar(
            delete(File).where(File.public_id == public_id, File.account_id == account_id).returning(File.id)
        )
