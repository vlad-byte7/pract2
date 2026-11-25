"""Проверки чтения CSV в обоих режимах."""

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import ConfigError, load_config


VALID_PACKAGE = "org.apache.commons:commons-text:1.11.0"
VALID_URL = "https://repo.maven.apache.org/maven2"


class ConfigTests(unittest.TestCase):
    """Проверяет корректные значения и сообщения об ошибках."""

    def load(self, content, fixture=False):
        """Читает конфигурацию из временного файла."""
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.csv"
            config.write_text(content, encoding="utf-8")
            if fixture:
                config.with_name("graph.txt").touch()
            return load_config(config)

    def test_maven_mode(self):
        result = self.load(
            f"package,{VALID_PACKAGE}\n"
            f"repository,{VALID_URL}\ntest_mode,false\n"
        )
        self.assertEqual(
            result,
            {
                "package": VALID_PACKAGE,
                "repository": VALID_URL,
                "test_mode": "false",
            },
        )

    def test_local_mode(self):
        result = self.load(
            "package,A\nrepository,graph.txt\ntest_mode,true\n", fixture=True
        )
        self.assertEqual(result["repository"], "graph.txt")
        self.assertEqual(result["test_mode"], "true")

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
                with self.assertRaisesRegex(ConfigError, field):
                    self.load(
                        f"package,{package}\n"
                        f"repository,{source}\ntest_mode,{mode}\n"
                    )

    def test_missing_setting(self):
        message = "отсутствует настройка repository"
        with self.assertRaisesRegex(ConfigError, message):
            self.load(f"package,{VALID_PACKAGE}\ntest_mode,false\n")

    def test_duplicate_setting(self):
        message = "настройка package указана дважды"
        with self.assertRaisesRegex(ConfigError, message):
            self.load("package,A\npackage,B\n")
