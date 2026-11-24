from pathlib import Path
import re
import subprocess
import sys
import tomllib

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
KNOWN_BAD_FIXTURE = "ty_fixture/known_bad.py"
TY_COMMAND = ("ty", "check", "--output-format", "concise", KNOWN_BAD_FIXTURE)
TY_TIMEOUT_SECONDS = 120
REPORTED_ERROR_RULE = re.compile(r": error\[([a-z-]+)\]")


def collect_error_level_rules() -> set[str]:
    project = tomllib.loads((BACKEND_DIRECTORY / "pyproject.toml").read_text(encoding="utf-8"))
    return {rule_name for rule_name, level in project["tool"]["ty"]["rules"].items() if level == "error"}


def collect_rules_reported_on_fixture() -> set[str]:
    completed = subprocess.run(  # noqa: S603  # a fixed command, no outside input
        TY_COMMAND,
        cwd=BACKEND_DIRECTORY,
        capture_output=True,
        text=True,
        timeout=TY_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    return set(REPORTED_ERROR_RULE.findall(completed.stdout))


def main() -> None:
    error_level_rules = collect_error_level_rules()
    silent_rules = sorted(error_level_rules - collect_rules_reported_on_fixture())
    for silent_rule in silent_rules:
        print(f"{silent_rule} reports no error in {KNOWN_BAD_FIXTURE}: the rule is off, or has no violation there")
    print(
        f"type rule fixture: {len(error_level_rules)} rules set to error, {len(silent_rules)} silent on the known-bad file"
    )
    sys.exit(1 if silent_rules else 0)


if __name__ == "__main__":
    main()
