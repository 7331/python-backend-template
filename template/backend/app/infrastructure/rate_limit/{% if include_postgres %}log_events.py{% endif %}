import logging

from app.shared.logging import LogEvent


class RateLimitStoreUnreachable(LogEvent):
    level = logging.WARNING
    message = "Postgres did not answer a rate-limit statement; each API process limits on its own until it does"
    operation = "rate_limit_check"
    error_type: str
