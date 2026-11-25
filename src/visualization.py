"""Преобразует список смежности в текст диаграммы D2."""

import json


def render_d2(graph):
    """Объявляет узлы и добавляет стрелки от пакетов к зависимостям."""
    ids = {package: f"pkg{i}" for i, package in enumerate(graph, start=1)}
    lines = ["direction: down", ""]
    for package, node_id in ids.items():
        lines.append(f"{node_id}: {json.dumps(package)}")

    for package, dependencies in graph.items():
        for dependency in dependencies:
            lines.append(f"{ids[package]} -> {ids[dependency]}")
    return "\n".join(lines)
