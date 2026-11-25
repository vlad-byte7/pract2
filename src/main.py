"""Запускает консольную программу для анализа зависимостей Maven."""

import argparse
import sys
from pathlib import Path

from config import ConfigError, load_config
from maven import MavenError, direct_dependencies


def main():
    """Читает настройки и выводит прямые зависимости пакета."""
    parser = argparse.ArgumentParser(description="Анализ зависимостей Maven")
    default_config = Path(__file__).resolve().parents[1] / "config.csv"
    parser.add_argument("config", type=Path, nargs="?", default=default_config)
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        if config["test_mode"] == "true":
            raise ConfigError("тестовый репозиторий будет поддержан на этапе 3")
        package = config["package"]
        dependencies = direct_dependencies(config["repository"], package)
    except (ConfigError, MavenError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1

    print(f"Прямые зависимости {package}:")
    if not dependencies:
        print("Зависимостей нет.")
    for dependency in dependencies:
        print(dependency)
    return 0


if __name__ == "__main__":
    sys.exit(main())
