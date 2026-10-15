"""GET /pherc lists every scroll in one call (#22).

Calls the handler directly with the DB mocked out, and checks routing against
the app's route table, so it needs no Neo4j or server.
"""
import asyncio
import json
import unittest
from unittest import mock

from starlette.routing import Match

from educelab import hercdb

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server

ROWS = [{"displayName": "1044", "literary_work": None, "unrolling_status": "Unrolled",
         "metadata": {"Author": {"name": "Philodemus"}}, "cornici_count": 3, "pezzi_count": 0}]


def route_for(path):
    """The endpoint a GET to *path* reaches, or None."""
    scope = {"type": "http", "method": "GET", "path": path}
    for route in server.app.routes:
        if route.matches(scope)[0] == Match.FULL:
            return route.endpoint
    return None


class TestListPhercsRoute(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)

    def test_routing(self):
        self.assertIs(route_for("/pherc"), server.list_phercs)
        # The per-PHerc path routes still reach their own handlers.
        self.assertIs(route_for("/pherc/1044/subdivisions"), server.get_subdivisions)

    def test_returns_rows(self):
        self.db.list_phercs.return_value = ROWS
        response = asyncio.run(server.list_phercs(user="t"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body), ROWS)

    def test_empty_is_200(self):
        self.db.list_phercs.return_value = []
        response = asyncio.run(server.list_phercs(user="t"))
        self.assertEqual((response.status_code, json.loads(response.body)), (200, []))


if __name__ == "__main__":
    unittest.main()
