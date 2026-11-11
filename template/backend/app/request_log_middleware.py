import time

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.log_events import RequestHandled
from app.shared import logging as log
from app.shared.request import read_route_template

logger = log.get_logger(__name__)


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # noqa: PLR0917  # ASGI interface
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        started = time.perf_counter()

        async def send_logged(message: Message) -> None:
            if message["type"] == "http.response.start":
                log.emit(
                    logger,
                    event=RequestHandled(
                        method=request.method,
                        route=read_route_template(request),
                        status_code=message["status"],
                        duration_milliseconds=round((time.perf_counter() - started) * 1000, 1),
                    ),
                )
            await send(message)

        await self.app(scope, receive, send_logged)
