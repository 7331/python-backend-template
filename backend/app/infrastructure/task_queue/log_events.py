import logging

from app.shared.logging import LogEvent


class WorkerStarted(LogEvent):
    message = "Worker started"
    operation = "worker_startup"
    job_kinds: list[str]


class WorkerStopped(LogEvent):
    message = "Worker stopped"
    operation = "worker_shutdown"


class JobSucceeded(LogEvent):
    message = "Job succeeded"
    operation = "job_run"
    job_id: int
    job_kind: str
    attempt_count: int
    duration_milliseconds: float


class JobRetryScheduled(LogEvent):
    level = logging.WARNING
    message = "Job raised; it runs again after the backoff"
    operation = "job_run"
    job_id: int
    job_kind: str
    attempt_count: int
    retry_in_seconds: float
    error_type: str


class JobFailed(LogEvent):
    level = logging.ERROR
    message = "Job used its last attempt; it stays failed with its last error"
    operation = "job_run"
    job_id: int
    job_kind: str
    attempt_count: int
    error_type: str


class JobReleased(LogEvent):
    message = "Worker is stopping; the job in hand went back to the queue without using an attempt"
    operation = "job_run"
    job_id: int
    job_kind: str


class JobOutcomeDropped(LogEvent):
    level = logging.WARNING
    message = "Job outcome dropped: the lease ran out and the job was claimed again"
    operation = "job_run"
    job_id: int
    job_kind: str
    attempt_count: int


class JobOutcomeNotRecorded(LogEvent):
    level = logging.ERROR
    message = "Could not record the job's outcome; the job is claimed again when its lease runs out"
    operation = "job_run"
    job_id: int
    job_kind: str


class JobClaimFailed(LogEvent):
    level = logging.WARNING
    message = "Could not claim the next job; trying again after the poll interval"
    operation = "job_claim"
