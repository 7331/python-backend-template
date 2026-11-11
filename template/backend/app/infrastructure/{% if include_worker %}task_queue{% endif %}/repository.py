from datetime import timedelta

from pydantic import JsonValue
from sqlalchemy import ColumnElement, and_, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.task_queue.enums import JobStatus
from app.infrastructure.task_queue.models import Job
from app.infrastructure.task_queue.types import ClaimedJob, ExpiredJob


def build_claim_fence(claimed_job: ClaimedJob) -> tuple[ColumnElement[bool], ...]:
    return (
        Job.id == claimed_job.job_id,
        Job.status == JobStatus.RUNNING,
        Job.attempt_count == claimed_job.attempt_count,
    )


class JobRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def insert_job(self, job_kind: str, *, payload: dict[str, JsonValue], maximum_attempts: int) -> int:
        inserted = await self.session.execute(
            insert(Job).values(kind=job_kind, payload=payload, maximum_attempts=maximum_attempts).returning(Job.id)
        )
        return inserted.scalar_one()

    async def fail_expired_jobs_without_attempts_left(self, *, last_error: str) -> list[ExpiredJob]:
        failed = await self.session.execute(
            update(Job)
            .where(
                Job.status == JobStatus.RUNNING,
                Job.lease_expires_at <= func.now(),
                Job.attempt_count >= Job.maximum_attempts,
            )
            .values(status=JobStatus.FAILED, lease_expires_at=None, last_error=last_error)
            .returning(Job.id, Job.kind, Job.attempt_count)
        )
        return [ExpiredJob(job_id=row.id, job_kind=row.kind, attempt_count=row.attempt_count) for row in failed]

    async def claim_next_job(self, *, lease: timedelta) -> ClaimedJob | None:
        next_job_id = (
            select(Job.id)
            .where(
                or_(
                    and_(Job.status == JobStatus.QUEUED, Job.run_at <= func.now()),
                    and_(Job.status == JobStatus.RUNNING, Job.lease_expires_at <= func.now()),
                ),
                Job.attempt_count < Job.maximum_attempts,
            )
            .order_by(Job.run_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        claimed = await self.session.execute(
            update(Job)
            .where(Job.id == next_job_id)
            .values(
                status=JobStatus.RUNNING, attempt_count=Job.attempt_count + 1, lease_expires_at=func.now() + lease
            )
            .returning(Job.id, Job.kind, Job.payload, Job.attempt_count, Job.maximum_attempts)
        )
        row = claimed.one_or_none()
        if row is None:
            return None
        return ClaimedJob(
            job_id=row.id,
            job_kind=row.kind,
            payload=row.payload,
            attempt_count=row.attempt_count,
            maximum_attempts=row.maximum_attempts,
        )

    async def delete_claimed_job(self, claimed_job: ClaimedJob) -> bool:
        deleted = await self.session.execute(delete(Job).where(*build_claim_fence(claimed_job)).returning(Job.id))
        return deleted.one_or_none() is not None

    async def requeue_claimed_job(self, claimed_job: ClaimedJob, *, retry_delay: timedelta, last_error: str) -> bool:
        requeued = await self.session.execute(
            update(Job)
            .where(*build_claim_fence(claimed_job))
            .values(
                status=JobStatus.QUEUED, run_at=func.now() + retry_delay, lease_expires_at=None, last_error=last_error
            )
            .returning(Job.id)
        )
        return requeued.one_or_none() is not None

    async def fail_claimed_job(self, claimed_job: ClaimedJob, *, last_error: str) -> bool:
        failed = await self.session.execute(
            update(Job)
            .where(*build_claim_fence(claimed_job))
            .values(status=JobStatus.FAILED, lease_expires_at=None, last_error=last_error)
            .returning(Job.id)
        )
        return failed.one_or_none() is not None

    async def release_claimed_job(self, claimed_job: ClaimedJob) -> bool:
        released = await self.session.execute(
            update(Job)
            .where(*build_claim_fence(claimed_job))
            .values(
                status=JobStatus.QUEUED,
                attempt_count=Job.attempt_count - 1,
                run_at=func.now(),
                lease_expires_at=None,
            )
            .returning(Job.id)
        )
        return released.one_or_none() is not None
