from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.lifespan.composition import open_api_resources
from app.lifespan.resources import ApiLifespanState
from app.log_events import ApplicationStarted, ApplicationStopped
from app.shared import logging as log
from app.starter.accounts.configuration import read_relying_party

logger = log.get_logger(__name__)


@asynccontextmanager
async def run_api_lifespan(application: FastAPI) -> AsyncGenerator[ApiLifespanState]:
    del application
    read_relying_party()
    async with open_api_resources() as resources:
        log.emit(logger, event=ApplicationStarted())
        try:
            yield {"resources": resources}
        finally:
            log.emit(logger, event=ApplicationStopped())
