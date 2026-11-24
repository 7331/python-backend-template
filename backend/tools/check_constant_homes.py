import ast
from pathlib import Path
import re
import sys

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
APPLICATION_DIRECTORY_NAME = "app"
READING_DIRECTORY_NAMES = (APPLICATION_DIRECTORY_NAME, "tools", "migrations")
CONSTANT_NAME = re.compile(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*")
MINIMUM_READING_MODULES_AWAY_FROM_HOME = 2
MISPLACED_CONSTANT_ALLOWLIST: frozenset[str] = frozenset()


def parse_reading_modules() -> dict[str, ast.Module]:
    return {
        module_path.relative_to(BACKEND_DIRECTORY).as_posix(): ast.parse(module_path.read_text(encoding="utf-8"))
        for reading_directory_name in READING_DIRECTORY_NAMES
        for module_path in sorted((BACKEND_DIRECTORY / reading_directory_name).rglob("*.py"))
    }


def collect_read_names(module: ast.Module) -> set[str]:
    return {
        read_name
        for node in ast.walk(module)
        for read_name in (
            [node.id]
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
            else [node.attr]
            if isinstance(node, ast.Attribute)
            else [node.name]
            if isinstance(node, ast.alias)
            else []
        )
    }


def list_constant_names(module: ast.Module) -> list[str]:
    return [
        target.id
        for statement in module.body
        for target in (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
            if isinstance(statement, ast.AnnAssign)
            else []
        )
        if isinstance(target, ast.Name) and CONSTANT_NAME.fullmatch(target.id)
    ]


def collect_misplaced_constants() -> set[str]:
    modules = parse_reading_modules()
    read_names_by_module_path = {module_path: collect_read_names(module) for module_path, module in modules.items()}
    return {
        f"{module_path}:{constant_name}"
        for module_path, module in modules.items()
        if module_path.startswith(f"{APPLICATION_DIRECTORY_NAME}/")
        for constant_name in list_constant_names(module)
        if constant_name not in read_names_by_module_path[module_path]
        and sum(
            constant_name in read_names
            for reading_module_path, read_names in read_names_by_module_path.items()
            if reading_module_path != module_path
        )
        < MINIMUM_READING_MODULES_AWAY_FROM_HOME
    }


def main() -> None:
    misplaced_constants = collect_misplaced_constants()
    new_constants = sorted(misplaced_constants - MISPLACED_CONSTANT_ALLOWLIST)
    stale_entries = sorted(MISPLACED_CONSTANT_ALLOWLIST - misplaced_constants)
    for new_constant in new_constants:
        print(
            f"{new_constant} is not read where it is defined and fewer than two other modules read it: "
            "move it into the module that reads it"
        )
    for stale_entry in stale_entries:
        print(f"{stale_entry} is no longer misplaced: delete it from the allowlist")
    print(f"constant homes: {len(new_constants)} misplaced constants, {len(stale_entries)} stale allowlist entries")
    sys.exit(1 if new_constants or stale_entries else 0)


if __name__ == "__main__":
    main()
