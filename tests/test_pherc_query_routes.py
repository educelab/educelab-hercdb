"""GET /subdivisions and /all-datasets take the PHerc as a query parameter (#24).

PHerc ids such as ``1007/1673`` contain a slash, which the path routes
``/pherc/{pherc_id}/...`` cannot match even URL-encoded (the server decodes
``%2F`` before routing). Calls the handlers directly with the DB mocked out, and
checks routing against the app's route table, so it needs no Neo4j or server.
"""
import asyncio
import json
import unittest
from unittest import mock

from fastapi import HTTPException
from starlette.routing import Match

from educelab import hercdb

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server

SLASH_ID = "1007/1673"
SUBDIVISIONS = {"pherc": {"displayName": SLASH_ID}, "cornici": [], "pezzi": []}
ARTIFACTS = [{"uuid": "u-1", "datasets": []}]


def route_for(path):
    """The endpoint a GET to *path* reaches, or None."""
    scope = {"type": "http", "method": "GET", "path": path}
    for route in server.app.routes:
        if route.matches(scope)[0] == Match.FULL:
            return route.endpoint
    return None


def body(response):
    return json.loads(response.body)


class TestPhercQueryRoutes(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)
        self.db.list_cornici_and_pezzi_for_pherc.return_value = SUBDIVISIONS
        self.db.find_all_datasets_for_pherc.return_value = ARTIFACTS

    def test_routing(self):
        # The bug: a slashed id never reaches the path-form handlers.
        self.assertIsNot(route_for(f"/pherc/{SLASH_ID}/subdivisions"), server.get_subdivisions)
        self.assertIsNot(route_for(f"/pherc/{SLASH_ID}/all-datasets"), server.get_all_datasets_for_pherc)
        # The fix: the query-param routes, whatever the id holds.
        self.assertIs(route_for("/subdivisions"), server.get_subdivisions_by_name)
        self.assertIs(route_for("/all-datasets"), server.get_all_datasets_by_name)

    def test_subdivisions_slash_id(self):
        response = asyncio.run(server.get_subdivisions_by_name(pherc=SLASH_ID, user="t"))
        self.assertEqual(body(response), SUBDIVISIONS)
        self.db.list_cornici_and_pezzi_for_pherc.assert_called_once_with(SLASH_ID)

    def test_subdivisions_unknown_is_404(self):
        self.db.list_cornici_and_pezzi_for_pherc.return_value = None
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(server.get_subdivisions_by_name(pherc="x", user="t"))
        self.assertEqual(caught.exception.status_code, 404)

    def test_all_datasets_slash_id_and_filters(self):
        response = asyncio.run(server.get_all_datasets_by_name(
            pherc=SLASH_ID, dataset_type="PGSRaw",
            newest_completed=True, released_only=True, user="t",
        ))
        self.assertEqual(body(response), {"pherc": SLASH_ID, "artifacts": ARTIFACTS})
        self.db.find_all_datasets_for_pherc.assert_called_once_with(
            SLASH_ID, ds_type=server.DatasetType.PGSRaw,
            newest_completed=True, released_only=True,
        )

    def test_all_datasets_bad_type_is_400(self):
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(server.get_all_datasets_by_name(
                pherc="1", dataset_type="Nope",
                newest_completed=False, released_only=False, user="t",
            ))
        self.assertEqual(caught.exception.status_code, 400)

    def test_path_routes_still_serve_plain_ids(self):
        self.assertIs(route_for("/pherc/1044/subdivisions"), server.get_subdivisions)
        self.assertIs(route_for("/pherc/1044/all-datasets"), server.get_all_datasets_for_pherc)
        asyncio.run(server.get_subdivisions("1044", user="t"))
        self.db.list_cornici_and_pezzi_for_pherc.assert_called_once_with("1044")


if __name__ == "__main__":
    unittest.main()
