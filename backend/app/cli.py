from pathlib import Path
from typing import Annotated

import typer
import uvicorn
import uvloop

from app.configuration import read_application_settings
from app.infrastructure.task_queue.client import enqueue_job
from app.lifespan.composition import open_process_resources
from app.lifespan.resources import ProcessRole
from app.shared.logging import configure_logging
from app.starter.queue_probe.jobs import QueueProbeOutcome, QueueProbePayload
from app.worker import run_worker

command_line = typer.Typer(no_args_is_help=True, add_completion=False, help="starter-app backend")


@command_line.callback()
def configure_command_line_logging() -> None:
    configure_logging(read_application_settings().log_level)


@command_line.command("serve-api")
def serve_api(
    host: Annotated[str, typer.Option()] = "0.0.0.0",  # noqa: S104  # the container's address; the reverse proxy reaches it over the compose network
    port: Annotated[int, typer.Option()] = 8000,
    reload: Annotated[bool, typer.Option("--reload")] = False,
) -> None:
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        loop="uvloop",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(Path(__file__).resolve().parent)],
        proxy_headers=False,
        server_header=False,
        access_log=False,
        log_config=None,
        timeout_graceful_shutdown=20,
    )


@command_line.command("run-worker")
def run_worker_process() -> None:
    uvloop.run(run_worker())


async def enqueue_queue_probe_job(payload: QueueProbePayload) -> int:
    async with (
        open_process_resources(process_role=ProcessRole.COMMAND) as process_resources,
        process_resources.database.session_factory() as session,
        session.begin(),
    ):
        return await enqueue_job(session, payload=payload)


@command_line.command("enqueue-queue-probe")
def enqueue_queue_probe(
    hold_seconds: Annotated[float, typer.Option()] = 0.0,
    outcome: Annotated[QueueProbeOutcome, typer.Option()] = QueueProbeOutcome.SUCCEED,
) -> None:
    typer.echo(uvloop.run(enqueue_queue_probe_job(QueueProbePayload(hold_seconds=hold_seconds, outcome=outcome))))


def run_command_line() -> None:
    command_line()
