import ast
from pathlib import Path
import re
import sys

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
APPLICATION_DIRECTORY = BACKEND_DIRECTORY / "app"
SERVICE_MODULE_STEM = re.compile(r"(.+_)?service")
FIXED_LENGTH_TUPLE_RETURN_ALLOWLIST: frozenset[str] = frozenset()


def is_fixed_length_tuple(annotation: ast.AST) -> bool:
    match annotation:
        case ast.Subscript(value=ast.Name(id="tuple"), slice=ast.Tuple(elts=[_, ast.Constant(value=last_member)])):
            return last_member is not Ellipsis
        case ast.Subscript(value=ast.Name(id="tuple")):
            return True
        case _:
            return False


def collect_fixed_length_tuple_returns() -> set[str]:
    return {
        f"{module_path.relative_to(BACKEND_DIRECTORY).as_posix()}:{node.name}"
        for module_path in sorted(APPLICATION_DIRECTORY.rglob("*.py"))
        if SERVICE_MODULE_STEM.fullmatch(module_path.stem)
        for node in ast.walk(ast.parse(module_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.returns is not None
        and any(is_fixed_length_tuple(annotation) for annotation in ast.walk(node.returns))
    }


def main() -> None:
    fixed_length_tuple_returns = collect_fixed_length_tuple_returns()
    new_returns = sorted(fixed_length_tuple_returns - FIXED_LENGTH_TUPLE_RETURN_ALLOWLIST)
    stale_entries = sorted(FIXED_LENGTH_TUPLE_RETURN_ALLOWLIST - fixed_length_tuple_returns)
    for new_return in new_returns:
        print(f"{new_return} returns a fixed-length tuple: a service returns a typed model, so name the tuple's parts")
    for stale_entry in stale_entries:
        print(f"{stale_entry} no longer returns a fixed-length tuple: delete it from the allowlist")
    print(f"service returns: {len(new_returns)} fixed-length tuples, {len(stale_entries)} stale allowlist entries")
    sys.exit(1 if new_returns or stale_entries else 0)


if __name__ == "__main__":
    main()
