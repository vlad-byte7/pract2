"""Проверяет вывод узлов, стрелок и режим D2."""

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from visualization import render_d2


class VisualizationTests(unittest.TestCase):
    """Проверяет представление общих, циклических и одиночных узлов."""

    def test_shared_dependency_and_maven_label(self):
        package = "org.demo:a:1.0"
        graph = {package: ("B", "C"), "B": ("D",), "C": ("D",), "D": ()}
        result = render_d2(graph).splitlines()
        self.assertEqual(result.count('pkg4: "D"'), 1)
        self.assertIn(f'pkg1: "{package}"', result)
        self.assertIn("pkg2 -> pkg4", result)
        self.assertIn("pkg3 -> pkg4", result)

    def test_cycle_is_preserved(self):
        result = render_d2({"E": ("F",), "F": ("E",)})
        self.assertIn("pkg1 -> pkg2", result)
        self.assertIn("pkg2 -> pkg1", result)

    def test_cli_d2_for_package_without_dependencies(self):
        result = subprocess.run(
            [
                sys.executable, str(ROOT / "src/main.py"),
                str(ROOT / "examples/leaf.csv"), "--d2",
            ],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "direction: down", "", 'pkg1: "D"',
        ])
