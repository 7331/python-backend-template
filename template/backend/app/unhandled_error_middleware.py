from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.shared import logging as log
from app.shared.errors import AppError
from app.shared.exception_handlers import build_app_error_response
from app.shared.log_events import UnhandledError
from app.shared.request import read_route_template

logger = log.get_logger(__name__)


class UnhandledErrorMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # noqa: PLR0917  # ASGI interface
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def send_tracking_start(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking_start)
        except Exception:
            if response_started:
                raise
            log.emit_with_current_traceback(logger, event=UnhandledError(route=read_route_template(Request(scope))))
            await build_app_error_response(AppError("internal server error"))(scope, receive, send)
