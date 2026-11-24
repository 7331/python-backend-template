from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
import secrets
import subprocess
import tempfile

from pydantic import BaseModel, ConfigDict

from flow_report import FlowCheckFailedError, FlowReport
from stack_commands import (
    REPOSITORY_DIRECTORY,
    ComposeStack,
    StackCommandFailedError,
    destroy_stack,
    find_free_local_port,
    prepare_compose_stack,
    read_container_logs,
    start_stack,
)

EVIDENCE_ROOT_DIRECTORY_NAME = "starter-app-e2e"
SUMMARY_FILE_NAME = "summary.txt"
CONTAINER_LOG_FILE_NAME = "containers.log"
GIT_COMMAND_TIMEOUT_SECONDS = 30


class FlowStage(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    flow_report: FlowReport
    compose_stack: ComposeStack
    api_publish_port: int


class FlowRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    flow_name: str
    started_at: datetime
    played_commit: str
    evidence_directory: Path


def read_git_output(git_arguments: list[str]) -> str:
    return subprocess.run(
        ["git", *git_arguments],
        cwd=REPOSITORY_DIRECTORY,
        capture_output=True,
        text=True,
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        check=True,
    ).stdout.strip()


def read_played_commit() -> str:
    head_commit = read_git_output(["rev-parse", "HEAD"])
    return f"{head_commit}-dirty" if read_git_output(["status", "--porcelain"]) else head_commit


def start_flow_run(flow_name: str) -> FlowRun:
    started_at = datetime.now(UTC)
    evidence_directory = (
        Path(tempfile.gettempdir())
        / EVIDENCE_ROOT_DIRECTORY_NAME
        / f"{started_at:%Y%m%dT%H%M%SZ}-{flow_name}-{secrets.token_hex(2)}"
    )
    evidence_directory.mkdir(parents=True)
    return FlowRun(
        flow_name=flow_name,
        started_at=started_at,
        played_commit=read_played_commit(),
        evidence_directory=evidence_directory,
    )


def keep_container_logs(flow_report: FlowReport, *, compose_stack: ComposeStack, evidence_directory: Path) -> None:
    try:
        (evidence_directory / CONTAINER_LOG_FILE_NAME).write_text(read_container_logs(compose_stack))
    except StackCommandFailedError as log_error:
        flow_report.record_check("container logs kept", passed=False, detail=str(log_error))


def remove_stack(flow_report: FlowReport, *, compose_stack: ComposeStack) -> None:
    try:
        destroy_stack(compose_stack)
    except StackCommandFailedError as cleanup_error:
        flow_report.record_check("cleanup", passed=False, detail=str(cleanup_error))


def write_summary(flow_run: FlowRun, *, flow_report: FlowReport) -> None:
    result = "PASS" if flow_report.has_passed() else "FAIL"
    summary_lines = [
        f"Flow: {flow_run.flow_name}",
        f"Started: {flow_run.started_at.isoformat(timespec='seconds')}",
        f"Commit played: {flow_run.played_commit}",
        f"Result: {result}, {flow_report.passed_check_count} checks passed and {flow_report.failed_check_count} failed",
        "",
        *flow_report.check_lines,
    ]
    (flow_run.evidence_directory / SUMMARY_FILE_NAME).write_text("\n".join(summary_lines) + "\n")
    print(f"Evidence: {flow_run.evidence_directory}", flush=True)


def play_flow(
    flow_name: str, *, flow_environment_lines: tuple[str, ...], walk_journey: Callable[[FlowStage], None]
) -> bool:
    flow_run = start_flow_run(flow_name)
    flow_report = FlowReport()
    api_publish_port = find_free_local_port()
    with tempfile.TemporaryDirectory() as environment_directory:
        compose_stack = prepare_compose_stack(
            Path(environment_directory),
            api_publish_port=api_publish_port,
            flow_environment_lines=flow_environment_lines,
        )
        try:
            start_stack(compose_stack)
            walk_journey(
                FlowStage(flow_report=flow_report, compose_stack=compose_stack, api_publish_port=api_publish_port)
            )
        except StackCommandFailedError as stack_error:
            flow_report.record_check("stack", passed=False, detail=str(stack_error))
        except FlowCheckFailedError:
            pass
        finally:
            keep_container_logs(
                flow_report, compose_stack=compose_stack, evidence_directory=flow_run.evidence_directory
            )
            remove_stack(flow_report, compose_stack=compose_stack)
            write_summary(flow_run, flow_report=flow_report)
    return flow_report.has_passed()
