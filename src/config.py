"""Read and validate the application's CSV settings."""

import csv
import re
from urllib.parse import urlsplit


REQUIRED_KEYS = ("package", "repository", "test_mode")
COLUMN_COUNT = 2
MAVEN_PACKAGE = re.compile(r"[\w.-]+:[\w.-]+:[\w.+-]+", re.ASCII)
TEST_PACKAGE = re.compile(r"[A-Z]")


class ConfigError(ValueError):
    """Report an invalid or unreadable configuration."""


def read_settings(path):
    """Read one key and value per CSV row."""
    settings = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, strict=True)
        for row in reader:
            if not row:
                continue
            if len(row) != COLUMN_COUNT:
                raise ConfigError(f"строка {reader.line_num}: нужно два столбца")
            key, value = (cell.strip() for cell in row)
            if key not in REQUIRED_KEYS:
                raise ConfigError(f"неизвестная настройка: {key!r}")
            if key in settings:
                raise ConfigError(f"настройка {key} указана дважды")
            if not value:
                raise ConfigError(f"настройка {key} пуста")
            settings[key] = value

    for key in REQUIRED_KEYS:
        if key not in settings:
            raise ConfigError(f"отсутствует настройка {key}")
    return settings


def validate_url(value):
    """Check that the repository address is an HTTP or HTTPS URL."""
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as error:
        raise ConfigError("repository: некорректный URL") from error

    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or any(char.isspace() for char in value)
        or url.netloc.endswith(":")
        or port == 0
    ):
        raise ConfigError("repository: нужен корректный URL с http:// или https://")


def validate_settings(settings, directory):
    """Validate the package and repository for the selected mode."""
    mode = settings["test_mode"].lower()
    if mode not in ("true", "false"):
        raise ConfigError("test_mode: допустимы только true и false")

    package = settings["package"]
    repository = settings["repository"]
    if mode == "true":
        if not TEST_PACKAGE.fullmatch(package):
            raise ConfigError("package: в тестовом режиме нужна буква A–Z")
        if not (directory / repository).is_file():
            raise ConfigError(f"repository: файл не найден: {repository}")
    else:
        if not MAVEN_PACKAGE.fullmatch(package):
            raise ConfigError("package: нужен формат groupId:artifactId:version")
        validate_url(repository)

    settings["test_mode"] = mode


def load_config(path):
    """Return validated settings in the order used by the console."""
    try:
        settings = read_settings(path)
        validate_settings(settings, path.parent)
    except (OSError, UnicodeError, csv.Error) as error:
        raise ConfigError(f"не удалось обработать {path}: {error}") from error
    return {key: settings[key] for key in REQUIRED_KEYS}
