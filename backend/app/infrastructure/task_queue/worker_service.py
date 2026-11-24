import asyncio
from collections.abc import Callable, Sequence
from datetime import timedelta
import secrets
import time

from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.postgres.client import Database
from app.infrastructure.task_queue.client import JobPayload
from app.infrastructure.task_queue.log_events import (
    JobClaimFailed,
    JobFailed,
    JobOutcomeDropped,
    JobOutcomeNotRecorded,
    JobReleased,
    JobRetryScheduled,
    JobSucceeded,
)
from app.infrastructure.task_queue.repository import JobRepository
from app.infrastructure.task_queue.types import ClaimedJob
from app.shared import logging as log

logger = log.get_logger(__name__)

RETRY_BACKOFF_BASE_SECONDS = 2.0
RETRY_BACKOFF_CEILING_SECONDS = 3600.0
RETRY_JITTER_MAXIMUM_FRACTION = 0.1
SHUTDOWN_GRACE_SECONDS = 10.0
LAST_ERROR_MAXIMUM_LENGTH = 1000
LEASE_EXPIRED_ERROR_TYPE = "JobLeaseExpiredError"
LEASE_EXPIRED_LAST_ERROR = f"{LEASE_EXPIRED_ERROR_TYPE}: the worker stopped answering during the last attempt"


class JobLeaseLostError(Exception):
    pass


class UnknownJobKindError(Exception):
    pass


def build_retry_delay(attempt_count: int, *, jitter_fraction: float) -> timedelta:
    backoff_seconds = min(RETRY_BACKOFF_BASE_SECONDS * 2 ** (attempt_count - 1), RETRY_BACKOFF_CEILING_SECONDS)
    return timedelta(seconds=backoff_seconds * (1 + jitter_fraction))


def describe_last_error(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"[:LAST_ERROR_MAXIMUM_LENGTH]


def build_payload_classes_by_kind(payload_classes: Sequence[type[JobPayload]]) -> dict[str, type[JobPayload]]:
    payload_classes_by_kind = {payload_class.kind: payload_class for payload_class in payload_classes}
    if len(payload_classes_by_kind) != len(payload_classes):
        raise ValueError("two job payload classes share one kind")
    return payload_classes_by_kind


class JobQueueWorker:
    def __init__(
        self,
        *,
        database: Database,
        payload_classes: Sequence[type[JobPayload]],
        poll_interval_seconds: float,
        job_timeout_seconds: float,
        job_lease_seconds: float,
        stop_requested: asyncio.Event,
        record_heartbeat: Callable[[], None],
    ) -> None:
        self.database = database
        self.payload_classes_by_kind = build_payload_classes_by_kind(payload_classes)
        self.poll_interval_seconds = poll_interval_seconds
        self.job_timeout_seconds = job_timeout_seconds
        self.job_lease = timedelta(seconds=job_lease_seconds)
        self.stop_requested = stop_requested
        self.record_heartbeat = record_heartbeat

    async def run_until_stopped(self) -> None:
        while not self.stop_requested.is_set():
            try:
                claimed_job = await self.claim_next_job()
            except (SQLAlchemyError, OSError) as claim_error:
                log.emit_with_traceback(logger, event=JobClaimFailed(), exception=claim_error)
                await self.wait_one_poll_interval()
                continue
            self.record_heartbeat()
            if claimed_job is None:
                await self.wait_one_poll_interval()
            else:
                await self.run_claimed_job(claimed_job)

    async def wait_one_poll_interval(self) -> None:
        try:
            async with asyncio.timeout(self.poll_interval_seconds):
                await self.stop_requested.wait()
        except TimeoutError:
            return

    async def claim_next_job(self) -> ClaimedJob | None:
        async with self.database.session_factory() as session, session.begin():
            repository = JobRepository(session=session)
            for expired_job in await repository.fail_expired_jobs_without_attempts_left(
                last_error=LEASE_EXPIRED_LAST_ERROR
            ):
                log.emit(
                    logger,
                    event=JobFailed(
                        job_id=expired_job.job_id,
                        job_kind=expired_job.job_kind,
                        attempt_count=expired_job.attempt_count,
                        error_type=LEASE_EXPIRED_ERROR_TYPE,
                    ),
                )
            return await repository.claim_next_job(lease=self.job_lease)

    async def run_claimed_job(self, claimed_job: ClaimedJob) -> None:
        started_at = time.monotonic()
        handler_task = asyncio.create_task(self.handle_claimed_job(claimed_job))
        stop_task = asyncio.create_task(self.stop_requested.wait())
        await asyncio.wait({handler_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
        stop_task.cancel()
        if not handler_task.done():
            await asyncio.wait({handler_task}, timeout=SHUTDOWN_GRACE_SECONDS)
        if not handler_task.done():
            handler_task.cancel()
            await asyncio.wait({handler_task})
        try:
            if handler_task.cancelled():
                await self.release_claimed_job(claimed_job)
                return
            handler_error = handler_task.exception()
            if handler_error is None:
                log.emit(
                    logger,
                    event=JobSucceeded(
                        job_id=claimed_job.job_id,
                        job_kind=claimed_job.job_kind,
                        attempt_count=claimed_job.attempt_count,
                        duration_milliseconds=round((time.monotonic() - started_at) * 1000, 1),
                    ),
                )
                return
            await self.record_failed_attempt(claimed_job, handler_error=handler_error)
        except (SQLAlchemyError, OSError) as record_error:
            log.emit_with_traceback(
                logger,
                event=JobOutcomeNotRecorded(job_id=claimed_job.job_id, job_kind=claimed_job.job_kind),
                exception=record_error,
            )

    async def handle_claimed_job(self, claimed_job: ClaimedJob) -> None:
        payload_class = self.payload_classes_by_kind.get(claimed_job.job_kind)
        if payload_class is None:
            raise UnknownJobKindError("no payload class is registered for the job's kind")
        payload = payload_class.model_validate(claimed_job.payload)
        async with (
            asyncio.timeout(self.job_timeout_seconds),
            self.database.session_factory() as session,
            session.begin(),
        ):
            await payload.run_job(session=session)
            if not await JobRepository(session=session).delete_claimed_job(claimed_job):
                raise JobLeaseLostError("the lease ran out before the job finished")

    async def release_claimed_job(self, claimed_job: ClaimedJob) -> None:
        async with self.database.session_factory() as session, session.begin():
            was_released = await JobRepository(session=session).release_claimed_job(claimed_job)
        self.emit_recorded_outcome(
            claimed_job,
            was_recorded=was_released,
            recorded_event=JobReleased(job_id=claimed_job.job_id, job_kind=claimed_job.job_kind),
            handler_error=None,
        )

    async def record_failed_attempt(self, claimed_job: ClaimedJob, *, handler_error: BaseException) -> None:
        last_error = describe_last_error(handler_error)
        error_type = type(handler_error).__name__
        if not claimed_job.has_attempts_left():
            async with self.database.session_factory() as session, session.begin():
                was_failed = await JobRepository(session=session).fail_claimed_job(claimed_job, last_error=last_error)
            self.emit_recorded_outcome(
                claimed_job,
                was_recorded=was_failed,
                recorded_event=JobFailed(
                    job_id=claimed_job.job_id,
                    job_kind=claimed_job.job_kind,
                    attempt_count=claimed_job.attempt_count,
                    error_type=error_type,
                ),
                handler_error=handler_error,
            )
            return
        retry_delay = build_retry_delay(
            claimed_job.attempt_count,
            jitter_fraction=secrets.SystemRandom().uniform(0, RETRY_JITTER_MAXIMUM_FRACTION),
        )
        async with self.database.session_factory() as session, session.begin():
            was_requeued = await JobRepository(session=session).requeue_claimed_job(
                claimed_job, retry_delay=retry_delay, last_error=last_error
            )
        self.emit_recorded_outcome(
            claimed_job,
            was_recorded=was_requeued,
            recorded_event=JobRetryScheduled(
                job_id=claimed_job.job_id,
                job_kind=claimed_job.job_kind,
                attempt_count=claimed_job.attempt_count,
                retry_in_seconds=round(retry_delay.total_seconds(), 3),
                error_type=error_type,
            ),
            handler_error=handler_error,
        )

    def emit_recorded_outcome(
        self,
        claimed_job: ClaimedJob,
        *,
        was_recorded: bool,
        recorded_event: log.LogEvent,
        handler_error: BaseException | None,
    ) -> None:
        if not was_recorded:
            log.emit(
                logger,
                event=JobOutcomeDropped(
                    job_id=claimed_job.job_id,
                    job_kind=claimed_job.job_kind,
                    attempt_count=claimed_job.attempt_count,
                ),
            )
        elif handler_error is None:
            log.emit(logger, event=recorded_event)
        else:
            log.emit_with_traceback(logger, event=recorded_event, exception=handler_error)
