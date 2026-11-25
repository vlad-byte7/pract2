"""Проверки второго этапа без подключения к внешнему репозиторию."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from main import main
from maven import MavenError, direct_dependencies


BASE = "https://example.test/maven2"
PACKAGE = "org.demo:app:1.0"
APP_PATH = "/org/demo/app/1.0/app-1.0.pom"


class MavenTests(unittest.TestCase):
    """Проверяет чтение прямых зависимостей и обработку ошибок."""

    def test_cli_direct_dependencies(self):
        pom = b"""
        <project xmlns="http://maven.apache.org/POM/4.0.0">
          <properties><core.version>2.1</core.version></properties>
          <dependencies>
            <dependency>
              <groupId>org.demo</groupId><artifactId>core</artifactId>
              <version>${core.version}</version>
            </dependency>
          </dependencies>
          <build><plugins><plugin><dependencies><dependency>
            <groupId>org.demo</groupId><artifactId>plugin-lib</artifactId>
            <version>5</version>
          </dependency></dependencies></plugin></plugins></build>
        </project>
        """
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.csv"
            config.write_text(
                f"package,{PACKAGE}\nrepository,{BASE}\ntest_mode,false\n",
                encoding="utf-8",
            )
            with (
                patch("sys.argv", ["main.py", str(config)]),
                patch("maven.urlopen", return_value=io.BytesIO(pom)) as request,
                redirect_stdout(output),
            ):
                self.assertEqual(main(), 0)

        self.assertEqual(output.getvalue().splitlines(), [
            f"Прямые зависимости {PACKAGE}:", "org.demo:core:2.1"
        ])
        request.assert_called_once_with(BASE + APP_PATH, timeout=10)

    def test_parent_and_bom(self):
        poms = {
            "app-1.0.pom": b"""
              <project><parent><groupId>org.demo</groupId>
                <artifactId>parent</artifactId><version>1</version>
              </parent><dependencies><dependency>
                <groupId>org.demo</groupId><artifactId>core</artifactId>
              </dependency></dependencies></project>
            """,
            "parent-1.pom": b"""
              <project><properties><test.version>3</test.version></properties>
              <dependencies><dependency>
                <groupId>org.demo</groupId><artifactId>tools</artifactId>
                <version>${test.version}</version>
              </dependency></dependencies>
              <dependencyManagement><dependencies><dependency>
                <groupId>org.demo</groupId><artifactId>bom</artifactId>
                <version>1</version><type>pom</type><scope>import</scope>
              </dependency></dependencies></dependencyManagement></project>
            """,
            "bom-1.pom": b"""
              <project><dependencyManagement><dependencies><dependency>
                <groupId>org.demo</groupId><artifactId>core</artifactId>
                <version>2</version>
              </dependency></dependencies></dependencyManagement></project>
            """,
        }

        def open_pom(url, timeout):
            return io.BytesIO(poms[url.rsplit("/", 1)[-1]])

        with patch("maven.urlopen", side_effect=open_pom) as request:
            actual = direct_dependencies(BASE, PACKAGE)
        self.assertEqual(actual, ["org.demo:tools:3", "org.demo:core:2"])
        self.assertEqual(request.call_count, len(poms))

    def test_no_dependencies(self):
        with patch("maven.urlopen", return_value=io.BytesIO(b"<project/>")):
            self.assertEqual(direct_dependencies(BASE, PACKAGE), [])

    def test_pom_not_found(self):
        missing = HTTPError(BASE + APP_PATH, 404, "Not Found", {}, None)
        with patch("maven.urlopen", side_effect=missing):
            with self.assertRaisesRegex(MavenError, "HTTP Error 404"):
                direct_dependencies(BASE, PACKAGE)

    def test_invalid_xml(self):
        with patch("maven.urlopen", return_value=io.BytesIO(b"<project>")):
            with self.assertRaisesRegex(MavenError, "не удалось прочитать POM"):
                direct_dependencies(BASE, PACKAGE)
