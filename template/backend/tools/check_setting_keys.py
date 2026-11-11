import importlib
from pathlib import Path
import pkgutil
import re
import sys

from pydantic_settings import BaseSettings

import app

REPOSITORY_DIRECTORY = Path(__file__).resolve().parents[2]
EXAMPLE_KEY = re.compile(r"^([A-Z][A-Z0-9_]*)=", re.MULTILINE)


def import_configuration_modules() -> None:
    for module in pkgutil.walk_packages(app.__path__, prefix="app."):
        if module.name.rsplit(".", maxsplit=1)[-1] == "configuration":
            importlib.import_module(module.name)


def list_settings_classes(settings_class: type[BaseSettings]) -> list[type[BaseSettings]]:
    return [
        descendant
        for subclass in settings_class.__subclasses__()
        for descendant in (subclass, *list_settings_classes(subclass))
    ]


def list_setting_keys(settings_class: type[BaseSettings]) -> list[str]:
    environment_prefix = settings_class.model_config.get("env_prefix", "")
    return [
        str(field.validation_alias or f"{environment_prefix}{field_name}").upper()
        for field_name, field in settings_class.model_fields.items()
    ]


def list_example_keys() -> set[str]:
    return {
        example_key
        for example_path in REPOSITORY_DIRECTORY.glob(".env*.example")
        for example_key in EXAMPLE_KEY.findall(example_path.read_text(encoding="utf-8"))
    }


def main() -> None:
    import_configuration_modules()
    setting_keys = {
        setting_key
        for settings_class in list_settings_classes(BaseSettings)
        if settings_class.__module__.startswith("app.")
        for setting_key in list_setting_keys(settings_class)
    }
    missing_keys = sorted(setting_keys - list_example_keys())
    for missing_key in missing_keys:
        print(f"{missing_key} is read by a settings class and is in no .env*.example file")
    print(f"setting keys: {len(setting_keys)} read, {len(missing_keys)} missing from the example env files")
    sys.exit(1 if missing_keys else 0)


if __name__ == "__main__":
    main()
