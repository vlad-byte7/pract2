"""Запускает консольную программу для анализа зависимостей Maven."""

import argparse
import sys
from functools import partial
from pathlib import Path

from config import ConfigError, load_config
from graph import GraphError, build_graph, load_test_repository
from maven import MavenError, runtime_dependencies


def load_graph(config_path):
    """Выбирает источник данных и запускает обход графа."""
    config = load_config(config_path)
    package = config["package"]
    repository = config["repository"]
    if config["test_mode"] == "true":
        packages = load_test_repository(config_path.parent / repository)
        if package not in packages:
            message = f"пакет {package} не найден в тестовом репозитории"
            raise GraphError(message)
        return build_graph(package, packages.__getitem__)

    dependencies_of = partial(runtime_dependencies, repository, cache={})
    return build_graph(package, dependencies_of)


def main():
    """Читает настройки и выводит граф зависимостей."""
    parser = argparse.ArgumentParser(description="Анализ зависимостей Maven")
    default_config = Path(__file__).resolve().parents[1] / "config.csv"
    parser.add_argument("config", type=Path, nargs="?", default=default_config)
    args = parser.parse_args()

    try:
        graph = load_graph(args.config)
    except (ConfigError, GraphError, MavenError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1

    print(f"Граф зависимостей {next(iter(graph))}:")
    for package, dependencies in graph.items():
        targets = ", ".join(dependencies) or "нет зависимостей"
        print(f"{package} -> {targets}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
