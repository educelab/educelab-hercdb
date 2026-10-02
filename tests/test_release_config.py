"""Release-flag settings: parsing of the default and the writer allow-list. No DB needed."""
import os
import unittest
from unittest import mock

from educelab.hercdb import config


class TestReleaseConfig(unittest.TestCase):

    def setUp(self):
        # Keep a developer's ~/.educedb out of it.
        patcher = mock.patch.object(config, "_load_config", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_is_true_when_unset(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HERCDB_RELEASE_DEFAULT", None)
            self.assertIs(config.release_default(), True)

    def test_default_from_env(self):
        for raw, expected in (("false", False), ("0", False), ("no", False),
                              ("true", True), ("1", True), ("YES", True)):
            with mock.patch.dict(os.environ, {"HERCDB_RELEASE_DEFAULT": raw}):
                self.assertIs(config.release_default(), expected, raw)

    def test_default_from_config_file(self):
        with mock.patch.object(config, "_load_config", return_value={"release_default": False}):
            os.environ.pop("HERCDB_RELEASE_DEFAULT", None)
            self.assertIs(config.release_default(), False)

    def test_writers_empty_when_unset(self):
        os.environ.pop("HERCDB_RELEASE_WRITERS", None)
        self.assertEqual(config.release_writers(), set())

    def test_writers_from_env_and_file(self):
        with mock.patch.dict(os.environ, {"HERCDB_RELEASE_WRITERS": " portal, admin ,"}):
            self.assertEqual(config.release_writers(), {"portal", "admin"})
        os.environ.pop("HERCDB_RELEASE_WRITERS", None)
        with mock.patch.object(config, "_load_config", return_value={"release_writers": ["portal"]}):
            self.assertEqual(config.release_writers(), {"portal"})


if __name__ == "__main__":
    unittest.main()
