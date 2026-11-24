from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.shared.errors import RequestBodyTooLargeError
from app.shared.exception_handlers import build_app_error_response
from app.shared.schemas import RequestBodyLimitParameters

MAXIMUM_REQUEST_BODY_BYTES = 64 * 1024
CLIENT_DISCONNECTED_MESSAGE: Message = {"type": "http.disconnect"}


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # noqa: PLR0917  # ASGI interface
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        refusal = build_app_error_response(
            RequestBodyTooLargeError(RequestBodyLimitParameters(maximum_bytes=MAXIMUM_REQUEST_BODY_BYTES))
        )
        declared_body_bytes = Headers(scope=scope).get("content-length", "")
        if declared_body_bytes.isdecimal() and int(declared_body_bytes) > MAXIMUM_REQUEST_BODY_BYTES:
            await refusal(scope, receive, send)
            return
        received_body_bytes = 0
        response_started = False
        request_refused = False

        async def receive_within_limit() -> Message:
            nonlocal received_body_bytes, request_refused
            if request_refused:
                return CLIENT_DISCONNECTED_MESSAGE
            message = await receive()
            if message["type"] == "http.request":
                received_body_bytes += len(message.get("body", b""))
            if received_body_bytes <= MAXIMUM_REQUEST_BODY_BYTES or response_started:
                return message
            request_refused = True
            await refusal(scope, receive, send)
            return CLIENT_DISCONNECTED_MESSAGE

        async def send_unless_refused(message: Message) -> None:
            nonlocal response_started
            if request_refused:
                return
            response_started = True
            await send(message)

        await self.app(scope, receive_within_limit, send_unless_refused)
