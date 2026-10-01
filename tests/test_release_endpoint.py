"""PUT /educelabid/{uuid}/datasets/released: who may call it and what it accepts.

Calls the handler directly with the DB mocked out, so it needs no Neo4j or server.
"""
import asyncio
import unittest
from unittest import mock

from fastapi import HTTPException

from educelab import hercdb
from educelab.hercdb.db import DatasetType

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server


def call(body, user="portal", writers=("portal",)):
    with mock.patch.object(hercdb.config, "release_writers", return_value=set(writers)):
        return asyncio.run(server.set_dataset_released("u-1", server.SetDatasetReleasedRequest(**body), user=user))


BODY = {"dataset_type": "PGSRaw", "path": "/a/b", "released": False}


class TestReleaseEndpoint(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)
        self.db.set_dataset_released.return_value = [{"path": "/a/b", "released": False}]

    def assertStatus(self, code, *args, **kwargs):
        with self.assertRaises(HTTPException) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.status_code, code)

    def test_writer_sets_flag_and_records_reviewer(self):
        response = call({**BODY, "released_by": "reviewer-a"})
        self.assertEqual(response.status_code, 200)
        self.db.set_dataset_released.assert_called_once_with("u-1", DatasetType.PGSRaw, "/a/b", False, "reviewer-a")

    def test_released_by_defaults_to_token_user(self):
        call(BODY)
        self.assertEqual(self.db.set_dataset_released.call_args.args[-1], "portal")

    def test_non_writer_is_forbidden(self):
        self.assertStatus(403, BODY, user="hpc")
        self.assertStatus(403, BODY, writers=())
        self.db.set_dataset_released.assert_not_called()

    def test_bad_or_flatbed_type_is_rejected(self):
        self.assertStatus(400, {**BODY, "dataset_type": "Nope"})
        self.assertStatus(400, {**BODY, "dataset_type": "FlatbedScan"})

    def test_no_match_is_404(self):
        self.db.set_dataset_released.return_value = []
        self.assertStatus(404, BODY)


if __name__ == "__main__":
    unittest.main()
