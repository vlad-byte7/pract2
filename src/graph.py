"""Строит граф зависимостей обходом в ширину."""

import csv
from collections import deque

from config import TEST_PACKAGE


class GraphError(ValueError):
    """Сообщает об ошибке чтения или обработки графа."""


def build_graph(package, dependencies_of):
    """Возвращает список смежности в порядке обхода BFS."""
    queue = deque([package])
    discovered = {package}
    graph = {}

    while queue:
        current = queue.popleft()
        dependencies = tuple(dict.fromkeys(dependencies_of(current)))
        graph[current] = dependencies
        for dependency in dependencies:
            if dependency not in discovered:
                discovered.add(dependency)
                queue.append(dependency)

    return graph


def _dependency_index(graph):
    """Считает зависимости каждого пакета и находит его потребителей."""
    remaining = {package: len(deps) for package, deps in graph.items()}
    consumers = {package: [] for package in graph}
    for package, dependencies in graph.items():
        for dependency in dependencies:
            consumers[dependency].append(package)
    return remaining, consumers


def dependency_load_order(graph):
    """Сортирует пакеты так, чтобы зависимости шли перед потребителями."""
    remaining, consumers = _dependency_index(graph)
    ready = deque(package for package in graph if not remaining[package])
    order = []
    while ready:
        package = ready.popleft()
        order.append(package)
        for consumer in consumers[package]:
            remaining[consumer] -= 1
            if not remaining[consumer]:
                ready.append(consumer)

    if len(order) != len(graph):
        blocked = ", ".join(package for package in graph if remaining[package])
        raise GraphError(f"граф содержит цикл, заблокированы пакеты: {blocked}")
    return order


def read_test_rows(file):
    """Считывает строки вида «пакет,зависимость,зависимость»."""
    graph = {}
    reader = csv.reader(file, strict=True)
    for line, row in enumerate(reader, start=1):
        if not row:
            continue
        packages = [name.strip() for name in row]
        if not all(TEST_PACKAGE.fullmatch(name) for name in packages):
            raise GraphError(f"строка {line}: используй латинские буквы A–Z")
        package, *dependencies = packages
        if package in graph:
            raise GraphError(f"строка {line}: пакет {package} указан дважды")
        graph[package] = dependencies
    return graph


def load_test_repository(path):
    """Читает тестовый CSV и проверяет, что все пакеты объявлены."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            graph = read_test_rows(file)
    except (OSError, UnicodeError, csv.Error) as error:
        raise GraphError(f"не удалось прочитать {path}: {error}") from error

    for package, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in graph:
                raise GraphError(f"{package}: пакет {dependency} не объявлен")
    return graph
