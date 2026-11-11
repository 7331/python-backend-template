import ast
from collections.abc import Callable
import io
from pathlib import Path
import re
import sys
import tokenize

from pydantic import BaseModel, ConfigDict

PYTHON_DIRECTIVE = re.compile(r"^#\s*(?:noqa\b|ty:|pragma\b|nosemgrep\b|fmt:|isort:|ruff:)")
SHELL_DIRECTIVE = re.compile(r"^#\s*shellcheck\b")
YAML_DIRECTIVE = re.compile(r"^#\s*(?:v\d[\w.]*\s*$|frozen:|zizmor:|yamllint\b)")
DOCKERFILE_DIRECTIVE = re.compile(r"^#\s*(?:syntax|escape|check)\s*=", re.IGNORECASE)
NO_DIRECTIVE = re.compile(r"(?!)")
LICENSE_LINE = re.compile(r"^#\s*@license\b")
UPSTREAM_BUG_LINK = re.compile(
    r"https?://(?:www\.)?(?:"
    r"github\.com/[^/\s]+/[^/\s]+/(?:issues|pull|discussions)/\d+"
    r"|gitlab\.com/\S+?/-/(?:issues|merge_requests)/\d+"
    r"|codeberg\.org/\S+?/(?:issues|pulls)/\d+"
    r"|bugs\.[a-z0-9.-]+\.[a-z]+/\S+"
    r"|bugzilla\.[a-z0-9.-]+/\S+"
    r"|crbug\.com/\S+"
    r")",
    re.IGNORECASE,
)
HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
BLOCK_SCALAR_INDICATOR = re.compile(r"(?:^|:\s+|-\s+)[|>][-+]?[0-9]?$")
SHELL_COMMENT_BOUNDARIES = " \t\n;(|&{"
CADDYFILE_COMMENT_BOUNDARIES = " \t\n{}"
YAML_QUOTE_BOUNDARIES = " \t[{,:-"
KEPT_COMMENTS = (
    "A name, a type or a smaller function says it. Kept: the reason on a linter suppression, the link to the "
    "upstream bug a workaround exists for, an @license line, a shebang, and a tool directive (noqa, ty, shellcheck, "
    "a pinned version, a Dockerfile parser directive)."
)
SHOWN_TEXT_LENGTH = 100


class Comment(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_number: int
    column: int
    text: str


class CommentSyntax(BaseModel):
    model_config = ConfigDict(frozen=True)

    list_comments: Callable[[str], list[Comment]]
    directive: re.Pattern[str]


def locate_comment(text: str, *, start: int, end: int) -> Comment:
    line_start = text.rfind("\n", 0, start) + 1
    return Comment(line_number=text.count("\n", 0, start) + 1, column=start - line_start, text=text[start:end])


def locate_line_end(text: str, *, start: int) -> int:
    line_end = text.find("\n", start)
    return len(text) if line_end < 0 else line_end


def list_python_comments(text: str) -> list[Comment]:
    return [
        Comment(line_number=token.start[0], column=token.start[1], text=token.string)
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
        if token.type == tokenize.COMMENT
    ]


def list_docstrings(text: str) -> list[Comment]:
    return [
        Comment(line_number=node.body[0].lineno, column=node.body[0].col_offset, text=docstring)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and (docstring := ast.get_docstring(node, clean=False)) is not None
    ]


def skip_heredoc_body(text: str, *, start: int, terminator: str, strips_tabs: bool) -> int:
    cursor = start
    while cursor < len(text):
        line_end = locate_line_end(text, start=cursor)
        line = text[cursor:line_end]
        cursor = min(line_end + 1, len(text))
        if (line.lstrip("\t") if strips_tabs else line) == terminator:
            break
    return cursor


def list_shell_comments(text: str) -> list[Comment]:
    comments: list[Comment] = []
    pending_heredocs: list[re.Match[str]] = []
    open_quote = ""
    cursor = 0
    while cursor < len(text):
        character = text[cursor]
        if character == "\n":
            cursor += 1
            for heredoc in pending_heredocs:
                cursor = skip_heredoc_body(
                    text, start=cursor, terminator=heredoc.group(2), strips_tabs=heredoc.group(0).startswith("<<-")
                )
            pending_heredocs.clear()
        elif character == "\\" and open_quote != "'":
            cursor += 2
        elif open_quote:
            open_quote = "" if character == open_quote else open_quote
            cursor += 1
        elif character in "'\"":
            open_quote = character
            cursor += 1
        elif text.startswith("<<", cursor) and not text.startswith("<<<", cursor):
            heredoc = HEREDOC_OPEN.match(text, cursor)
            if heredoc:
                pending_heredocs.append(heredoc)
            cursor = heredoc.end() if heredoc else cursor + 2
        elif (
            character == "#"
            and (cursor == 0 or text[cursor - 1] in SHELL_COMMENT_BOUNDARIES)
            and not text.startswith("${", max(0, cursor - 2))
        ):
            line_end = locate_line_end(text, start=cursor)
            comments.append(locate_comment(text, start=cursor, end=line_end))
            cursor = line_end
        else:
            cursor += 1
    return comments


def find_yaml_comment_column(line: str) -> int | None:
    open_quote = ""
    column = 0
    while column < len(line):
        character = line[column]
        if open_quote:
            if character == "\\" and open_quote == '"':
                column += 1
            elif character == open_quote:
                open_quote = ""
        elif character in "'\"" and (column == 0 or line[column - 1] in YAML_QUOTE_BOUNDARIES):
            open_quote = character
        elif character == "#" and (column == 0 or line[column - 1] in " \t"):
            return column
        column += 1
    return None


def list_yaml_comments(text: str) -> list[Comment]:
    comments: list[Comment] = []
    block_scalar_indentation: int | None = None
    for line_number, line in enumerate(text.split("\n"), start=1):
        indentation = len(line) - len(line.lstrip(" "))
        if block_scalar_indentation is not None and (not line.strip() or indentation > block_scalar_indentation):
            continue
        block_scalar_indentation = None
        comment_column = find_yaml_comment_column(line)
        code = line if comment_column is None else line[:comment_column]
        if comment_column is not None:
            comments.append(Comment(line_number=line_number, column=comment_column, text=line[comment_column:]))
        if BLOCK_SCALAR_INDICATOR.search(code.rstrip()):
            block_scalar_indentation = indentation
    return comments


def list_dockerfile_comments(text: str) -> list[Comment]:
    return [
        Comment(line_number=line_number, column=len(line) - len(line.lstrip()), text=line.strip())
        for line_number, line in enumerate(text.split("\n"), start=1)
        if line.lstrip().startswith("#")
    ]


def list_caddyfile_comments(text: str) -> list[Comment]:
    comments: list[Comment] = []
    open_quote = ""
    cursor = 0
    while cursor < len(text):
        character = text[cursor]
        if open_quote:
            cursor += 2 if character == "\\" and open_quote == '"' else 1
            open_quote = "" if character == open_quote else open_quote
        elif character in '"`':
            open_quote = character
            cursor += 1
        elif character == "#" and (cursor == 0 or text[cursor - 1] in CADDYFILE_COMMENT_BOUNDARIES):
            line_end = locate_line_end(text, start=cursor)
            comments.append(locate_comment(text, start=cursor, end=line_end))
            cursor = line_end
        else:
            cursor += 1
    return comments


PYTHON_SYNTAX = CommentSyntax(list_comments=list_python_comments, directive=PYTHON_DIRECTIVE)
SHELL_SYNTAX = CommentSyntax(list_comments=list_shell_comments, directive=SHELL_DIRECTIVE)
YAML_SYNTAX = CommentSyntax(list_comments=list_yaml_comments, directive=YAML_DIRECTIVE)
DOCKERFILE_SYNTAX = CommentSyntax(list_comments=list_dockerfile_comments, directive=DOCKERFILE_DIRECTIVE)
CADDYFILE_SYNTAX = CommentSyntax(list_comments=list_caddyfile_comments, directive=NO_DIRECTIVE)
SYNTAX_BY_SUFFIX = {
    ".py": PYTHON_SYNTAX,
    ".sh": SHELL_SYNTAX,
    ".yml": YAML_SYNTAX,
    ".yaml": YAML_SYNTAX,
}
SYNTAX_BY_FILE_NAME = {
    "Dockerfile": DOCKERFILE_SYNTAX,
    "Caddyfile": CADDYFILE_SYNTAX,
}


def pick_comment_syntax(path: Path) -> CommentSyntax | None:
    return SYNTAX_BY_SUFFIX.get(path.suffix) or SYNTAX_BY_FILE_NAME.get(path.name)


def is_kept(comment: Comment, *, directive: re.Pattern[str]) -> bool:
    if comment.line_number == 1 and comment.column == 0 and comment.text.startswith("#!"):
        return True
    return any(pattern.search(comment.text) for pattern in (directive, UPSTREAM_BUG_LINK, LICENSE_LINE))


def list_refused_comments(path: Path) -> list[Comment]:
    comment_syntax = pick_comment_syntax(path)
    if comment_syntax is None:
        return []
    text = path.read_text(encoding="utf-8")
    refused_comments = [
        comment
        for comment in comment_syntax.list_comments(text)
        if not is_kept(comment, directive=comment_syntax.directive)
    ]
    if path.suffix == ".py":
        refused_comments.extend(list_docstrings(text))
    return refused_comments


def main() -> None:
    paths = [Path(argument) for argument in sys.argv[1:]]
    findings = [
        f"{path}:{comment.line_number}: {comment.text.splitlines()[0][:SHOWN_TEXT_LENGTH]}"
        for path in paths
        if path.is_file()
        for comment in list_refused_comments(path)
    ]
    for finding in findings:
        print(finding)
    print(f"comments: {len(findings)} findings in {len(paths)} files")
    if findings:
        print(KEPT_COMMENTS)
        sys.exit(1)


if __name__ == "__main__":
    main()
