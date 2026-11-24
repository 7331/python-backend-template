from annotationlib import get_annotations
import importlib
from pathlib import Path
import pkgutil
import re
import sys

from pydantic_settings import BaseSettings

import app

REPOSITORY_DIRECTORY = Path(__file__).resolve().parents[2]
EXAMPLE_KEY = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)
CONFIGURATION_MODULE_STEM = re.compile(r"(.+_)?configuration")


def import_configuration_modules() -> None:
    for module in pkgutil.walk_packages(app.__path__, prefix="app."):
        if CONFIGURATION_MODULE_STEM.fullmatch(module.name.rsplit(".", maxsplit=1)[-1]):
            importlib.import_module(module.name)


def list_settings_classes(settings_class: type[BaseSettings]) -> list[type[BaseSettings]]:
    return [
        descendant
        for subclass in settings_class.__subclasses__()
        for descendant in (subclass, *list_settings_classes(subclass))
    ]


def list_declared_setting_keys(settings_class: type[BaseSettings]) -> list[str]:
    environment_prefix = settings_class.model_config.get("env_prefix", "")
    return [
        str(field.validation_alias or f"{environment_prefix}{field_name}").upper()
        for field_name, field in settings_class.model_fields.items()
        if field_name in get_annotations(settings_class)
    ]


def collect_owners_by_setting_key() -> dict[str, list[str]]:
    owners_by_setting_key: dict[str, list[str]] = {}
    for settings_class in list_settings_classes(BaseSettings):
        if settings_class.__module__.startswith("app."):
            for setting_key in list_declared_setting_keys(settings_class):
                owners_by_setting_key.setdefault(setting_key, []).append(settings_class.__qualname__)
    return owners_by_setting_key


def collect_example_keys() -> set[str]:
    return {
        example_key
        for example_path in REPOSITORY_DIRECTORY.glob(".env*.example")
        for example_key in EXAMPLE_KEY.findall(example_path.read_text(encoding="utf-8"))
    }


def main() -> None:
    import_configuration_modules()
    owners_by_setting_key = collect_owners_by_setting_key()
    missing_keys = sorted(owners_by_setting_key.keys() - collect_example_keys())
    shared_keys = sorted(setting_key for setting_key, owners in owners_by_setting_key.items() if len(owners) > 1)
    for missing_key in missing_keys:
        print(f"{missing_key} is read by a settings class and is in no .env*.example file")
    for shared_key in shared_keys:
        print(
            f"{shared_key} is declared by {' and '.join(sorted(owners_by_setting_key[shared_key]))}: "
            "an environment key has one settings class that owns it"
        )
    print(
        f"setting keys: {len(owners_by_setting_key)} read, {len(missing_keys)} missing from the example env files, "
        f"{len(shared_keys)} declared by more than one settings class"
    )
    sys.exit(1 if missing_keys or shared_keys else 0)


if __name__ == "__main__":
    main()
