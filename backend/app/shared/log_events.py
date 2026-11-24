import logging

from app.shared.logging import LogEvent


class UnhandledError(LogEvent):
    level = logging.ERROR
    message = "Unhandled error"
    operation = "request_error"
    route: str
