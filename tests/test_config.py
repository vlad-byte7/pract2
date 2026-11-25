"""Check success and failure through the console entry point."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MAIN = Path(__file__).resolve().parents[1] / "src" / "main.py"
VALID_PACKAGE = "org.apache.commons:commons-text:1.11.0"
VALID_URL = "https://repo.maven.apache.org/maven2"


class ConfigTests(unittest.TestCase):
    """Exercise configurations in both repository modes."""

    def run_config(self, content, fixture=False):
        """Write a temporary config and run the program against it."""
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.csv"
            config.write_text(content, encoding="utf-8")
            if fixture:
                config.with_name("graph.txt").touch()
            return subprocess.run(
                [sys.executable, "-X", "utf8", str(MAIN), str(config)],
                capture_output=True,
                encoding="utf-8",
                check=False,
            )

    def test_maven_mode(self):
        result = self.run_config(
            f"package,{VALID_PACKAGE}\nrepository,{VALID_URL}\ntest_mode,false\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                f"package = {VALID_PACKAGE}",
                f"repository = {VALID_URL}",
                "test_mode = false",
            ],
        )

    def test_local_mode(self):
        result = self.run_config(
            "package,A\nrepository,graph.txt\ntest_mode,true\n",
            fixture=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("repository = graph.txt", result.stdout)

    def test_invalid_settings(self):
        cases = [
            ("wrong", VALID_URL, "false", "package:"),
            (VALID_PACKAGE, "maven2", "false", "repository:"),
            (VALID_PACKAGE, VALID_URL, "yes", "test_mode:"),
            ("A", "missing.txt", "true", "repository:"),
            ("AA", "graph.txt", "true", "package:"),
        ]
        for package, source, mode, field in cases:
            with self.subTest(package=package, source=source, mode=mode):
                result = self.run_config(
                    f"package,{package}\nrepository,{source}\ntest_mode,{mode}\n"
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(field, result.stderr)

    def test_missing_setting(self):
        result = self.run_config(f"package,{VALID_PACKAGE}\ntest_mode,false\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("отсутствует настройка repository", result.stderr)

    def test_duplicate_setting(self):
        result = self.run_config("package,A\npackage,B\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("настройка package указана дважды", result.stderr)
