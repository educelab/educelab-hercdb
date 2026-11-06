"""Release-flag settings, and how ~/.educedb's sections are read (#81). No DB needed.

Run: uv run python -m unittest tests.test_release_config
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from educelab.hercdb import config

ENV = ("HERCDB_RELEASE_DEFAULT", "HERCDB_RELEASE_WRITERS")


class TestReleaseConfig(unittest.TestCase):
    """The two settings, from the environment or a [release] section."""

    def setUp(self):
        # Keep a developer's ~/.educedb and environment out of it.
        patcher = mock.patch.object(config, "_load_sections", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for key in ENV:
            os.environ.pop(key, None)

    def sections(self, sections):
        return mock.patch.object(config, "_load_sections", return_value=sections)

    def test_default_is_true_when_unset(self):
        self.assertIs(config.release_default(), True)

    def test_default_from_env(self):
        for raw, expected in (("false", False), ("0", False), ("no", False),
                              ("true", True), ("1", True), ("YES", True)):
            with mock.patch.dict(os.environ, {"HERCDB_RELEASE_DEFAULT": raw}):
                self.assertIs(config.release_default(), expected, raw)

    def test_default_from_release_section(self):
        with self.sections({"database": {}, "release": {"default": False}}):
            self.assertIs(config.release_default(), False)
        with self.sections({"database": {}, "release": {"default": "false"}}):  # configparser
            self.assertIs(config.release_default(), False)

    def test_writers_empty_when_unset(self):
        self.assertEqual(config.release_writers(), set())

    def test_writers_from_env(self):
        with mock.patch.dict(os.environ, {"HERCDB_RELEASE_WRITERS": " portal, admin ,"}):
            self.assertEqual(config.release_writers(), {"portal", "admin"})

    def test_writers_from_release_section(self):
        for value in (["portal", "admin"],      # TOML
                      '["portal", "admin"]',    # the same line, as configparser reads it
                      "portal, admin"):
            with self.subTest(value=value), self.sections({"release": {"writers": value}}):
                self.assertEqual(config.release_writers(), {"portal", "admin"})

    def test_env_overrides_the_file(self):
        with self.sections({"release": {"writers": ["portal"], "default": True}}), \
                mock.patch.dict(os.environ, {"HERCDB_RELEASE_WRITERS": "admin",
                                             "HERCDB_RELEASE_DEFAULT": "false"}):
            self.assertEqual(config.release_writers(), {"admin"})
            self.assertIs(config.release_default(), False)


class _TempHome(unittest.TestCase):
    """A test whose ~/.educedb lives in a temporary directory."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        home = mock.patch.object(config.Path, "home", return_value=self.home)
        home.start()
        self.addCleanup(home.stop)
        config._load_sections.cache_clear()
        self.addCleanup(config._load_sections.cache_clear)


@unittest.skipIf(sys.version_info < (3, 11), "reads ~/.educedb with tomllib")
class TestConfigFile(_TempHome):
    """~/.educedb itself: which section is which."""

    def load(self, text):
        (self.home / ".educedb").write_text(text)
        config._load_sections.cache_clear()
        return config._load_sections()

    def test_database_and_release_sections(self):
        sections = self.load('[database]\nuri = "neo4j://x:7687"\n\n'
                             '[release]\nwriters = ["portal"]\ndefault = false\n')
        self.assertEqual(config._load_config(), {"uri": "neo4j://x:7687"})
        self.assertEqual(sections["release"], {"writers": ["portal"], "default": False})

    def test_first_section_is_the_database_whatever_its_name(self):
        self.load('[hercdb]\nuri = "neo4j://x:7687"\n')
        self.assertEqual(config._load_config(), {"uri": "neo4j://x:7687"})

    def test_release_first_still_finds_the_database(self):
        self.load('[release]\nwriters = ["portal"]\n\n[database]\nuri = "neo4j://x:7687"\n')
        self.assertEqual(config._load_config(), {"uri": "neo4j://x:7687"})

    def test_top_level_keys_are_the_database(self):
        self.load('uri = "neo4j://x:7687"\n\n[release]\nwriters = ["portal"]\n')
        self.assertEqual(config._load_config(), {"uri": "neo4j://x:7687"})

    def test_empty_file(self):
        self.assertEqual(self.load(""), {})
        self.assertEqual(config._load_config(), {})

    def test_no_file(self):
        config._load_sections.cache_clear()
        self.assertIsNone(config._load_config())

    def test_quiet_when_everything_is_read(self):
        with self.assertNoLogs("educelab.hercdb", "WARNING"):
            self.load('[hercdb]\nuri = "x"\n\n[release]\nwriters = ["portal"]\n')

    def test_warns_on_an_unread_section(self):
        with self.assertLogs("educelab.hercdb", "WARNING") as logs:
            self.load('[database]\nuri = "x"\n\n[neo4j]\nuri = "y"\n')
        self.assertIn("section [neo4j] is not read", logs.output[0])


class TestConfigparserReader(_TempHome):

    def test_configparser_reader(self):
        """What Python 3.10, which has no tomllib, reads from the same file."""
        path = self.home / ".educedb"
        path.write_text('[database]\nuri = "neo4j://x:7687"\n\n'
                        '[release]\nwriters = ["portal", "admin"]\ndefault = false\n')
        sections = config._read_ini(path)
        with mock.patch.object(config, "_load_sections", return_value=sections), \
                mock.patch.dict(os.environ):
            for key in ENV:
                os.environ.pop(key, None)
            self.assertEqual(config.release_writers(), {"portal", "admin"})
            self.assertIs(config.release_default(), False)


if __name__ == "__main__":
    unittest.main()
