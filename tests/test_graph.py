"""Проверяет обход графа и работу двух источников зависимостей."""

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from graph import GraphError, build_graph, read_test_rows
from main import load_graph


class GraphTests(unittest.TestCase):
    """Проверяет порядок BFS, циклы и источники данных."""

    def test_breadth_first_order(self):
        packages = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": ["A"]}
        calls = []

        def dependencies_of(package):
            calls.append(package)
            return packages[package]

        graph = build_graph("A", dependencies_of)
        self.assertEqual(calls, ["A", "B", "C", "D"])
        self.assertEqual(graph["B"], ("D",))
        self.assertEqual(graph["C"], ("D",))
        self.assertEqual(graph["D"], ("A",))

    def test_repository_rows_reject_duplicates(self):
        with self.assertRaisesRegex(GraphError, "пакет A указан дважды"):
            read_test_rows(io.StringIO("A,B\nA\n"))

    def test_cli_examples(self):
        examples = {
            "branching": [
                "Граф зависимостей A:",
                "A -> B, C",
                "B -> D",
                "C -> D",
                "D -> нет зависимостей",
            ],
            "cycle": ["Граф зависимостей E:", "E -> F", "F -> E"],
            "isolated": ["Граф зависимостей G:", "G -> нет зависимостей"],
        }
        for name, lines in examples.items():
            with self.subTest(name=name):
                result = subprocess.run(
                    [
                        sys.executable, "-X", "utf8", str(ROOT / "src/main.py"),
                        str(ROOT / "examples" / f"{name}.csv"),
                    ],
                    capture_output=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), lines)

    def test_cli_load_order(self):
        cases = {
            "branching": (0, "D -> B -> C"),
            "cycle": (1, "граф содержит цикл"),
            "isolated": (0, "Нет зависимостей."),
        }
        for name, (exit_code, message) in cases.items():
            with self.subTest(name=name):
                config = ROOT / "examples" / f"{name}.csv"
                result = subprocess.run(
                    [
                        sys.executable, "-X", "utf8", str(ROOT / "src/main.py"),
                        str(config), "--load-order",
                    ],
                    capture_output=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, exit_code, result.stderr)
                if exit_code:
                    self.assertEqual(result.stdout, "")
                    self.assertIn(message, result.stderr)
                else:
                    self.assertEqual(result.stdout.splitlines()[-1], message)

    def test_maven_runtime_graph(self):
        root = "org.apache.commons:commons-text:1.11.0"
        core = "org.demo:core:2"
        leaf = "org.demo:leaf:3"
        root_pom = b"""
        <project><dependencies>
          <dependency><groupId>org.demo</groupId><artifactId>core</artifactId>
            <version>2</version>
          </dependency>
          <dependency><groupId>org.demo</groupId><artifactId>test</artifactId>
            <version>2</version><scope>test</scope>
          </dependency>
          <dependency><groupId>org.demo</groupId><artifactId>extra</artifactId>
            <version>2</version><optional>true</optional>
          </dependency>
        </dependencies></project>
        """
        core_pom = b"""
        <project><dependencies><dependency>
          <groupId>org.demo</groupId><artifactId>leaf</artifactId>
          <version>3</version><scope>runtime</scope>
        </dependency></dependencies></project>
        """
        with tempfile.TemporaryDirectory() as directory, patch(
            "maven.urlopen"
        ) as request:
            request.side_effect = [
                io.BytesIO(pom) for pom in (root_pom, core_pom, b"<project/>")
            ]
            config = Path(directory, "config.csv")
            config.write_text(
                f"package,{root}\n"
                "repository,https://example.test/maven2\n"
                "test_mode,false\n",
                encoding="utf-8",
            )
            graph = load_graph(config)

        self.assertEqual(graph, {root: (core,), core: (leaf,), leaf: ()})
        self.assertEqual(request.call_count, 3)
