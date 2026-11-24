import math
import time

MAXIMUM_TRACKED_SCOPES = 100_000


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self.theoretical_arrival_times: dict[str, float] = {}

    def count_seconds_until_admitted(self, scope: str, *, limit: int, window_seconds: int) -> int:
        now = time.monotonic()
        if len(self.theoretical_arrival_times) > MAXIMUM_TRACKED_SCOPES:
            self.forget_idle_scopes(now=now)
        interval_seconds = window_seconds / limit
        theoretical_arrival_time = max(self.theoretical_arrival_times.get(scope, now), now)
        next_theoretical_arrival_time = theoretical_arrival_time + interval_seconds
        allowed_at = next_theoretical_arrival_time - window_seconds
        if now < allowed_at:
            return max(1, math.ceil(allowed_at - now))
        self.theoretical_arrival_times[scope] = next_theoretical_arrival_time
        return 0

    def forget_idle_scopes(self, *, now: float) -> None:
        self.theoretical_arrival_times = {
            scope: arrival_time for scope, arrival_time in self.theoretical_arrival_times.items() if arrival_time > now
        }
