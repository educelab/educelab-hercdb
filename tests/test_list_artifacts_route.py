"""GET /artifacts with no parameters lists every artifact (#21).

With ``pherc`` it still returns one artifact's detail; ``cornice`` or ``pezzo``
without ``pherc`` is still a 422. Calls the handler directly with the DB mocked
out, so it needs no Neo4j or server.
"""
import asyncio
import json
import unittest
from unittest import mock

from fastapi import HTTPException

from educelab import hercdb

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server

ROWS = [{"uuid": "u-1", "type": "Cornice", "datasets": {}, "catalogue": {}}]
DETAIL = {"displayName": "2", "type": "PHerc"}


def call(**params):
    params = {"pherc": None, "cornice": None, "pezzo": None, **params}
    return asyncio.run(server.get_artifact_by_name(**params, user="t"))


class TestListArtifactsRoute(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)
        self.db.list_artifacts.return_value = ROWS
        self.db.get_artifact_info.return_value = DETAIL

    def test_no_params_lists(self):
        response = call()
        self.assertEqual((response.status_code, json.loads(response.body)), (200, ROWS))
        self.db.get_artifact_info.assert_not_called()

    def test_empty_list_is_200(self):
        self.db.list_artifacts.return_value = []
        self.assertEqual(json.loads(call().body), [])

    def test_pherc_still_gives_detail(self):
        self.assertEqual(json.loads(call(pherc="2").body), DETAIL)
        self.db.get_artifact_info.assert_called_once_with("2", cornice=None, pezzo=None)
        self.db.list_artifacts.assert_not_called()

    def test_subdivision_without_pherc_is_422(self):
        for params in ({"cornice": "1"}, {"pezzo": "1"}):
            with self.subTest(**params), self.assertRaises(HTTPException) as caught:
                call(**params)
            self.assertEqual(caught.exception.status_code, 422)
        self.db.list_artifacts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
