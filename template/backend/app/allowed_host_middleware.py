from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.shared.errors import HostNotAllowedError
from app.shared.exception_handlers import build_app_error_response

HOST_ALLOWED_MESSAGE_TYPE = "app.host_allowed"


async def report_allowed_host(scope: Scope, receive: Receive, send: Send) -> None:  # noqa: PLR0917  # ASGI interface
    del scope, receive
    await send({"type": HOST_ALLOWED_MESSAGE_TYPE})


class AllowedHostMiddleware:
    def __init__(self, app: ASGIApp, *, allowed_hosts: tuple[str, ...]) -> None:
        self.app = app
        self.host_check = TrustedHostMiddleware(report_allowed_host, allowed_hosts=allowed_hosts, www_redirect=False)
        self.checked_app = TrustedHostMiddleware(app, allowed_hosts=allowed_hosts, www_redirect=False)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # noqa: PLR0917  # ASGI interface
        if scope["type"] != "http":
            await self.checked_app(scope, receive, send)
            return
        host_is_allowed = False

        async def record_host_verdict(message: Message) -> None:
            nonlocal host_is_allowed
            host_is_allowed = host_is_allowed or message["type"] == HOST_ALLOWED_MESSAGE_TYPE

        await self.host_check(scope, receive, record_host_verdict)
        if host_is_allowed:
            await self.app(scope, receive, send)
            return
        refusal = build_app_error_response(HostNotAllowedError("the Host header names no host this service answers for"))
        await refusal(scope, receive, send)
