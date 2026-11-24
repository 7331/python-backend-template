from uuid import uuid4

from asgi_correlation_id.context import correlation_id
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ServerMintedCorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:  # noqa: PLR0917  # ASGI interface
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        minted_correlation_id = uuid4().hex
        correlation_id.set(minted_correlation_id)

        async def send_with_correlation_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                MutableHeaders(scope=message).append("X-Request-ID", minted_correlation_id)
            await send(message)

        await self.app(scope, receive, send_with_correlation_header)
