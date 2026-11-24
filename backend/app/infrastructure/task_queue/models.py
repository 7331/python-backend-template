from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.postgres.models import Base, SurrogateId, Timestamps, build_postgres_enum
from app.infrastructure.task_queue.enums import JobStatus

JOB_KIND_MAXIMUM_LENGTH = 128


class Job(SurrogateId, Timestamps, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_queued_run_at", "run_at", "id", postgresql_where=text("status = 'queued'")),
        Index("ix_jobs_running_lease_expires_at", "lease_expires_at", postgresql_where=text("status = 'running'")),
    )

    kind: Mapped[str] = mapped_column(String(JOB_KIND_MAXIMUM_LENGTH))
    payload: Mapped[dict[str, JsonValue]] = mapped_column(JSONB)
    status: Mapped[JobStatus] = mapped_column(
        build_postgres_enum(JobStatus, name="job_status"), server_default=JobStatus.QUEUED.value
    )
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="0")
    maximum_attempts: Mapped[int] = mapped_column(Integer)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
