import argparse
from pathlib import Path
import re
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PULL_REQUEST_TITLE_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/pr-title.yml"
PATTERN_LINE = re.compile(r"^\s*pattern='(?P<pattern>[^']+)'\s*$", re.MULTILINE)
SUBJECTS_GIT_WRITES = re.compile(r'^(Merge |Revert "|Reapply "|(fixup|squash|amend)! )')


def read_pull_request_title_pattern() -> re.Pattern[str]:
    patterns = PATTERN_LINE.findall(PULL_REQUEST_TITLE_WORKFLOW.read_text())
    if len(patterns) != 1:
        raise SystemExit(
            f"{PULL_REQUEST_TITLE_WORKFLOW.relative_to(REPOSITORY_ROOT)} must hold exactly one line pattern='...' "
            f"(found {len(patterns)}): the commit-msg hook reads the title rule from it"
        )
    return re.compile(patterns[0])


def read_commit_subject(commit_message_path: Path) -> str:
    for line in commit_message_path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            return line
    return ""


def main() -> None:
    argument_parser = argparse.ArgumentParser(description="Check a commit subject against the PR title rule.")
    argument_parser.add_argument("commit_message_path", type=Path, nargs="?", help="the file git wrote the message to")
    commit_message_path = argument_parser.parse_args().commit_message_path
    title_pattern = read_pull_request_title_pattern()
    if commit_message_path is None:
        return
    subject = read_commit_subject(commit_message_path)
    if not subject or title_pattern.match(subject) or SUBJECTS_GIT_WRITES.match(subject):
        return
    sys.stderr.write(
        "The commit subject must match the PR title rule in .github/workflows/pr-title.yml, "
        "so a pull request titled from it passes 'Conventional title'.\n"
        f"  pattern: {title_pattern.pattern}\n  got:     {subject}\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
