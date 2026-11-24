import random
import re
from typing import cast

from ty_fixture.possibly_missing import possibly_missing_name


def read_matched_text(match: re.Match) -> str:
    return match.string


def refuse_wrong_separator(record: bytes) -> None:
    if record[0] != b"\x1e":
        raise ValueError(record)


def read_unknown_name() -> int:
    return unknown_name  # ty: ignore


def convert_count_to_text(count: int) -> str:
    return cast(str, count)


class Parent:
    def read_number(self) -> int:
        return 1


class Child(Parent):
    def read_number(self) -> int:
        return 2


def read_possibly_unbound_name() -> int:
    if random.random() > 0.5:
        chosen_number = 1
    return chosen_number


class PossiblyIncomplete:
    if random.random() > 0.5:
        attribute: int = 1


def read_possibly_missing_attribute() -> int:
    return PossiblyIncomplete.attribute + possibly_missing_name
