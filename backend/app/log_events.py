import logging

from app.shared.logging import LogEvent


class ApplicationStarted(LogEvent):
    message = "Application started"
    operation = "api_lifespan_startup"


class ApplicationStopped(LogEvent):
    message = "Application stopped"
    operation = "api_lifespan_shutdown"


class RequestHandled(LogEvent):
    message = "Request handled"
    operation = "request"
    method: str
    route: str
    status_code: int
    duration_milliseconds: float


class ForwardedClientAddressIgnored(LogEvent):
    level = logging.WARNING
    message = "X-Real-IP ignored: it came from a private peer that is not a trusted proxy"
    operation = "client_ip_address"
    peer_ip_address: str
