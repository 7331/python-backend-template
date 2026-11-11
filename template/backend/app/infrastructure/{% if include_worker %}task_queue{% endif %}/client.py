from typing import ClassVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.task_queue.repository import JobRepository

DEFAULT_MAXIMUM_ATTEMPTS = 5


class JobPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ClassVar[str]
    maximum_attempts: ClassVar[int] = DEFAULT_MAXIMUM_ATTEMPTS

    async def run_job(self, *, session: AsyncSession) -> None:
        raise NotImplementedError


async def enqueue_job(session: AsyncSession, *, payload: JobPayload) -> int:
    return await JobRepository(session=session).insert_job(
        payload.kind, payload=payload.model_dump(mode="json"), maximum_attempts=payload.maximum_attempts
    )
