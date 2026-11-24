import asyncio
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from starlette.middleware.base import BaseHTTPMiddleware

from app.lifespan.resources import Resources
from app.shared.schemas import ErrorDetail

application = FastAPI()
logger = application.logger

logger.info("typed-log-emission")
logger.bind(rule="typed-log-context")


class KeepsResources:
    def __init__(self, resources: Resources) -> None:
        self.resources = resources

    @staticmethod
    def build_nothing() -> None:
        return None

    def _read_privately(self) -> None:
        return None


def copy_exception_text(error: Exception) -> None:
    raise ValueError(str(error))


application.state.database = None
ErrorDetail(code="code", pointer="/").model_copy(update={"code": "other"})
ErrorDetail(code="code", pointer="/").model_dump(exclude={"pointer"})
isinstance(application.title, str)
isinstance(application, ErrorDetail)
Direction = Literal["up", "down"]


class ReadsAttributes(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccountView(BaseModel):
    username: str


async def run_on_the_default_executor() -> None:
    await asyncio.get_running_loop().run_in_executor(None, copy_exception_text)


application.add_middleware(BaseHTTPMiddleware)


@application.middleware("http")
async def wrap_request(request: object, call_next: object) -> None:
    return None


def name_an_abbreviation(req: object, *, cfg: object) -> None:
    msg = "abbreviated"
    for i in range(3):
        msg = f"{msg}{i}{req}{cfg}"
    try:
        copy_exception_text(ValueError(msg))
    except ValueError as e:
        raise RuntimeError from e
