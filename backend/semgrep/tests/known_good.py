import asyncio
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
import hmac
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from starlette.types import ASGIApp, Receive, Scope, Send

from app.shared import logging as log
from app.shared.errors import AppError
from app.shared.schemas import ErrorDetail

application = FastAPI()
logger = log.get_logger(__name__)
thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="known-good")


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"


SingleTag = Literal["only"]
UpOnly = Literal[Direction.UP]


class AccountResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    message_identifier: str
    request_index: int


class KeepsCollaborators:
    def __init__(self, *, thread_pool: ThreadPoolExecutor) -> None:
        self.thread_pool = thread_pool

    def __repr__(self) -> str:
        return "KeepsCollaborators"

    def read_openly(self) -> None:
        return None


class PureAsgiMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)


def raise_a_safe_message(error: Exception) -> None:
    raise ValueError("the value is not valid") from error


def emit_typed_events(event: log.LogEvent) -> None:
    log.emit(logger, event=event)
    hmac.new(b"key", b"message", "sha256")


def build_and_dump(error_detail: ErrorDetail) -> None:
    ErrorDetail(code="other", pointer=error_detail.pointer).model_dump()
    isinstance(error_detail, AppError)


async def run_on_a_named_executor() -> None:
    task = asyncio.get_running_loop().run_in_executor(thread_pool, application.openapi)
    await task
    task.exception()


def spell_names_out(request: object, *, configuration: object) -> None:
    message = "whole words"
    express_response = f"{message}{request}{configuration}"
    for index in range(3):
        message = f"{express_response}{index}"
    try:
        raise_a_safe_message(ValueError(message))
    except ValueError as error:
        raise RuntimeError from error


application.add_middleware(PureAsgiMiddleware)
