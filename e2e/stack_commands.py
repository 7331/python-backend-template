from pathlib import Path
import secrets
import socket
import subprocess

from pydantic import BaseModel, ConfigDict

REPOSITORY_DIRECTORY = Path(__file__).resolve().parent.parent
E2E_COMPOSE_PROJECT_NAME_PREFIX = "starter-app-e2e"
STACK_START_TIMEOUT_SECONDS = 600
STACK_STOP_TIMEOUT_SECONDS = 120
CONTAINER_LOG_READ_TIMEOUT_SECONDS = 60
DATABASE_READ_TIMEOUT_SECONDS = 30


class StackCommandFailedError(Exception):
    pass


class ComposeStack(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_name: str
    environment_file: Path


def find_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        return probe_socket.getsockname()[1]


def find_database_owner_environment_file(environment_file: Path) -> Path:
    return environment_file.with_name("e2e.database-owner.env")


def write_database_owner_environment_file(environment_file: Path) -> None:
    database_owner_environment_file = find_database_owner_environment_file(environment_file)
    database_owner_environment_file.write_text(f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}\n")
    database_owner_environment_file.chmod(0o600)


def build_public_base_url(api_publish_port: int) -> str:
    return f"http://localhost:{api_publish_port}"


def prepare_compose_stack(
    environment_directory: Path, *, api_publish_port: int, flow_environment_lines: tuple[str, ...]
) -> ComposeStack:
    environment_file = environment_directory / "e2e.env"
    object_storage_publish_port = find_free_local_port()
    environment_lines = [
        f"STARTER_ENVIRONMENT_FILE={environment_file}",
        f"STARTER_DATABASE_OWNER_ENVIRONMENT_FILE={find_database_owner_environment_file(environment_file)}",
        f"STARTER_APPLICATION_DATABASE_PASSWORD={secrets.token_urlsafe(24)}",
        f"STARTER_ACCOUNTS_PUBLIC_BASE_URL={build_public_base_url(api_publish_port)}",
        f"API_PUBLISH_PORT={api_publish_port}",
        f"STARTER_OBJECT_STORAGE_ACCESS_KEY_ID={secrets.token_hex(12)}",
        f"STARTER_OBJECT_STORAGE_SECRET_ACCESS_KEY={secrets.token_urlsafe(32)}",
        f"STARTER_OBJECT_STORAGE_PUBLIC_ENDPOINT_URL=http://127.0.0.1:{object_storage_publish_port}",
        f"OBJECT_STORAGE_PUBLISH_PORT={object_storage_publish_port}",
        *flow_environment_lines,
    ]
    environment_file.write_text("\n".join(environment_lines) + "\n")
    environment_file.chmod(0o600)
    write_database_owner_environment_file(environment_file)
    return ComposeStack(
        project_name=f"{E2E_COMPOSE_PROJECT_NAME_PREFIX}-{secrets.token_hex(4)}", environment_file=environment_file
    )


def run_compose(
    compose_arguments: list[str],
    *,
    compose_stack: ComposeStack,
    timeout_seconds: int,
    input_text: str | None = None,
) -> str:
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            compose_stack.project_name,
            "--env-file",
            str(compose_stack.environment_file),
            "--file",
            "docker-compose.yml",
            *compose_arguments,
        ],
        cwd=REPOSITORY_DIRECTORY,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise StackCommandFailedError(
            f"docker compose {compose_arguments[:2]} exited {completed.returncode}: {completed.stderr.strip()[-400:]}"
        )
    return completed.stdout


def start_stack(compose_stack: ComposeStack) -> None:
    run_compose(
        ["up", "--detach", "--build", "--wait", "--wait-timeout", "300"],
        compose_stack=compose_stack,
        timeout_seconds=STACK_START_TIMEOUT_SECONDS,
    )


def destroy_stack(compose_stack: ComposeStack) -> None:
    run_compose(
        ["down", "--volumes", "--remove-orphans"],
        compose_stack=compose_stack,
        timeout_seconds=STACK_STOP_TIMEOUT_SECONDS,
    )


def read_container_logs(compose_stack: ComposeStack) -> str:
    return run_compose(
        ["logs", "--no-color", "--timestamps"],
        compose_stack=compose_stack,
        timeout_seconds=CONTAINER_LOG_READ_TIMEOUT_SECONDS,
    )


def read_database_value(sql_query: str, *, compose_stack: ComposeStack) -> str:
    return run_compose(
        [
            "exec",
            "-T",
            "--env",
            "PGOPTIONS=-c default_transaction_read_only=on",
            "postgres",
            "psql",
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            "starterapp",
            "--dbname",
            "starterapp",
        ],
        compose_stack=compose_stack,
        timeout_seconds=DATABASE_READ_TIMEOUT_SECONDS,
        input_text=sql_query,
    ).strip()
