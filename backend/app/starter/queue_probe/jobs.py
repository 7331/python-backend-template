import asyncio
from enum import StrEnum
from typing import override

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.task_queue.client import JobPayload

QUEUE_PROBE_MAXIMUM_HOLD_SECONDS = 600.0


class QueueProbeOutcome(StrEnum):
    SUCCEED = "succeed"
    RAISE = "raise"


class QueueProbeFailedError(Exception):
    pass


class QueueProbePayload(JobPayload):
    kind = "queue_probe.probe"
    maximum_attempts = 3

    hold_seconds: float = Field(ge=0, le=QUEUE_PROBE_MAXIMUM_HOLD_SECONDS)
    outcome: QueueProbeOutcome

    @override
    async def run_job(self, *, session: AsyncSession) -> None:
        await asyncio.sleep(self.hold_seconds)
        if self.outcome is QueueProbeOutcome.RAISE:
            raise QueueProbeFailedError("the queue probe was asked to raise")
