import logging

from app.shared.logging import LogEvent


class DatabaseClosed(LogEvent):
    message = "Database connections closed"
    operation = "database_close"


class DatabaseUnreachable(LogEvent):
    level = logging.WARNING
    message = "Database did not answer the readiness check"
    operation = "database_readiness_check"
    error_type: str
