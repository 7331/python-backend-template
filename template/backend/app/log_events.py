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
