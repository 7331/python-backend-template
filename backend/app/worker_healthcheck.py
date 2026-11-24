from pathlib import Path
import sys
import time

from app.infrastructure.task_queue.configuration import read_task_queue_settings

WORKER_HEARTBEAT_PATH = Path("/tmp/worker-heartbeat")  # noqa: S108  # the worker container's own tmpfs, shared with nothing


def is_worker_alive() -> bool:
    try:
        heartbeat_age_seconds = time.time() - WORKER_HEARTBEAT_PATH.stat().st_mtime
    except OSError:
        return False
    return heartbeat_age_seconds < read_task_queue_settings().get_heartbeat_stale_after_seconds()


if __name__ == "__main__":
    sys.exit(0 if is_worker_alive() else 1)
