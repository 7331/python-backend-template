import ast
from pathlib import Path
import re
import subprocess
import sys
import tomllib

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
VULTURE_TIMEOUT_SECONDS = 120
VULTURE_EXIT_CODE_FOR_DEAD_CODE = 3
UNUSED_VARIABLE_FINDING = re.compile(r"^(?P<path>.+?):(?P<line>\d+): unused variable '[^']+' \(\d+% confidence\)$")
SERIALIZED_MODEL_BASE_NAMES = frozenset({"ApiResponse", "LogEvent"})
COLUMN_ANNOTATION_NAME = "Mapped"


def find_expression_name(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Subscript):
        return find_expression_name(expression.value)
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        return expression.attr
    return None


def list_scanned_module_paths() -> list[Path]:
    project = tomllib.loads((BACKEND_DIRECTORY / "pyproject.toml").read_text(encoding="utf-8"))
    scanned_paths = [BACKEND_DIRECTORY / scanned_path for scanned_path in project["tool"]["vulture"]["paths"]]
    return sorted(
        module_path
        for scanned_path in scanned_paths
        for module_path in (scanned_path.rglob("*.py") if scanned_path.is_dir() else [scanned_path])
    )


def list_classes(modules: dict[str, ast.Module]) -> list[tuple[str, ast.ClassDef]]:
    return [
        (relative_path, node)
        for relative_path, module in modules.items()
        for node in ast.walk(module)
        if isinstance(node, ast.ClassDef)
    ]


def is_serialized_model(
    class_name: str, *, base_names_by_class_name: dict[str, set[str]], seen: frozenset[str]
) -> bool:
    return class_name in SERIALIZED_MODEL_BASE_NAMES or any(
        is_serialized_model(base_name, base_names_by_class_name=base_names_by_class_name, seen=seen | {class_name})
        for base_name in base_names_by_class_name.get(class_name, set()) - seen
    )


def collect_field_locations(modules: dict[str, ast.Module]) -> set[tuple[str, int]]:
    classes = list_classes(modules)
    base_names_by_class_name: dict[str, set[str]] = {}
    for _, class_node in classes:
        base_names_by_class_name.setdefault(class_node.name, set()).update(
            base_name for base_name in map(find_expression_name, class_node.bases) if base_name is not None
        )
    return {
        (relative_path, statement.lineno)
        for relative_path, class_node in classes
        for statement in class_node.body
        if isinstance(statement, ast.AnnAssign)
        and (
            find_expression_name(statement.annotation) == COLUMN_ANNOTATION_NAME
            or is_serialized_model(class_node.name, base_names_by_class_name=base_names_by_class_name, seen=frozenset())
        )
    }


def is_field_finding(finding: str, *, field_locations: set[tuple[str, int]]) -> bool:
    unused_variable = UNUSED_VARIABLE_FINDING.fullmatch(finding)
    return (
        unused_variable is not None
        and (Path(unused_variable["path"]).as_posix(), int(unused_variable["line"])) in field_locations
    )


def main() -> None:
    completed = subprocess.run(
        ("vulture",),
        cwd=BACKEND_DIRECTORY,
        capture_output=True,
        text=True,
        timeout=VULTURE_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode not in {0, VULTURE_EXIT_CODE_FOR_DEAD_CODE}:
        sys.stderr.write(completed.stdout + completed.stderr)
        raise SystemExit(completed.returncode)
    field_locations = collect_field_locations(
        {
            module_path.relative_to(BACKEND_DIRECTORY).as_posix(): ast.parse(module_path.read_text(encoding="utf-8"))
            for module_path in list_scanned_module_paths()
        }
    )
    reported_findings = completed.stdout.splitlines()
    findings = [
        finding for finding in reported_findings if not is_field_finding(finding, field_locations=field_locations)
    ]
    for finding in findings:
        print(finding)
    print(
        f"dead code: {len(findings)} findings, "
        f"{len(reported_findings) - len(findings)} response, log-event and column fields counted as used"
    )
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
