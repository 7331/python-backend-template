import ast
from pathlib import Path
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
MIGRATIONS_DIRECTORY = BACKEND_DIRECTORY / "migrations"
REVISION_DIRECTORY_NAMES = ("template_versions", "versions")


def read_script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(BACKEND_DIRECTORY / "alembic.ini")))


def list_revision_paths() -> list[Path]:
    return sorted(
        revision_path
        for revision_directory_name in REVISION_DIRECTORY_NAMES
        for revision_path in (MIGRATIONS_DIRECTORY / revision_directory_name).glob("*.py")
    )


def has_raising_downgrade(revision_path: Path) -> bool:
    return any(
        isinstance(node, ast.FunctionDef)
        and node.name == "downgrade"
        and any(isinstance(statement, ast.Raise) for statement in node.body)
        for node in ast.parse(revision_path.read_text(encoding="utf-8")).body
    )


def main() -> None:
    script_directory = read_script_directory()
    heads = sorted(script_directory.get_heads())
    bases = sorted(script_directory.get_bases())
    revision_paths = list_revision_paths()
    problems = [
        f"{revision_path.name}: downgrade() must raise, because migrations are forward only"
        for revision_path in revision_paths
        if not has_raising_downgrade(revision_path)
    ]
    if len(heads) != len(bases):
        problems.append(
            f"every line must have exactly one head, found {len(bases)} lines ({', '.join(bases)}) "
            f"and {len(heads)} heads ({', '.join(heads)})"
        )
    for problem in problems:
        print(problem)
    print(
        f"migrations: {len(revision_paths)} revisions, {len(bases)} lines, {len(heads)} heads, {len(problems)} problems"
    )
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
