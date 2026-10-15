"""Dataset reads return an empty result, not 404, for a known id with no datasets (#25).

``GET /educelabid/{uuid}/datasets`` and ``GET /all-datasets?pherc=`` (and its
path form) 404 only when the EduceLabID or PHerc does not exist. Calls the
handlers directly with the DB mocked out, so it needs no Neo4j or server.
"""
import asyncio
import json
import unittest
from unittest import mock

from fastapi import HTTPException

from educelab import hercdb

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server

NO_FILTERS = {"dataset_type": None, "newest_completed": False, "released_only": False}


def educelabid(uuid="u-1", **filters):
    return asyncio.run(server.get_datasets_for_educelabid(uuid, **{**NO_FILTERS, **filters}, user="t"))


def all_datasets(pherc="1044", **filters):
    return asyncio.run(server.get_all_datasets_by_name(pherc=pherc, **{**NO_FILTERS, **filters}, user="t"))


def body(response):
    return json.loads(response.body)


class TestEmptyDatasetReads(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)
        self.db.find_datasets_for_educelabid_with_predecessors.return_value = []
        self.db.find_all_datasets_for_pherc.return_value = []
        self.db.educelabid_exists.return_value = True
        self.db.pherc_exists.return_value = True

    def assert404(self, call, *args):
        with self.assertRaises(HTTPException) as caught:
            call(*args)
        self.assertEqual(caught.exception.status_code, 404)

    def test_known_educelabid_without_datasets_is_empty_list(self):
        response = educelabid()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body(response), [])
        self.db.educelabid_exists.assert_called_once_with("u-1")

    def test_unknown_educelabid_is_404(self):
        self.db.educelabid_exists.return_value = False
        self.assert404(educelabid)

    def test_educelabid_with_datasets_skips_existence_check(self):
        self.db.find_datasets_for_educelabid_with_predecessors.return_value = [{"type": "PGSRaw"}]
        self.assertEqual(body(educelabid()), [{"type": "PGSRaw"}])
        self.db.educelabid_exists.assert_not_called()

    def test_filter_matching_nothing_is_empty_list(self):
        self.assertEqual(body(educelabid(dataset_type="Registered", newest_completed=True)), [])

    def test_known_pherc_without_datasets_is_empty(self):
        response = all_datasets()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body(response), {"pherc": "1044", "artifacts": []})
        self.db.pherc_exists.assert_called_once_with("1044")

    def test_unknown_pherc_is_404(self):
        self.db.pherc_exists.return_value = False
        self.assert404(all_datasets)

    def test_path_form_shares_the_rule(self):
        self.db.pherc_exists.return_value = False
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(server.get_all_datasets_for_pherc("nope", **NO_FILTERS, user="t"))
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
