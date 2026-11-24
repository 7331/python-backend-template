import argparse
from pathlib import Path
import sys

import orjson

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app


def dump_openapi_document(output_path: Path) -> None:
    document = create_app().openapi()
    output_path.write_bytes(orjson.dumps(document, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n")


def main() -> None:
    argument_parser = argparse.ArgumentParser(description="Write the API's OpenAPI document as JSON.")
    argument_parser.add_argument("output_path", type=Path, help="the file to write")
    dump_openapi_document(argument_parser.parse_args().output_path)


if __name__ == "__main__":
    main()
