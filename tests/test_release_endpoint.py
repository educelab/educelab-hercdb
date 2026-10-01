"""PUT /datasets/{dataset_uuid}/released: who may call it and what it answers.

Calls the handler directly with the DB mocked out, so it needs no Neo4j or server.
"""
import asyncio
import unittest
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError

from educelab import hercdb

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server

DATASET = {"type": "PGSRaw", "uuid": "d-1", "path": "/a/b", "released": False}


def call(body, user="portal", writers=("portal",)):
    with mock.patch.object(hercdb.config, "release_writers", return_value=set(writers)):
        return asyncio.run(server.set_dataset_released("d-1", server.SetDatasetReleasedRequest(**body), user=user))


class TestReleaseEndpoint(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)
        self.db.set_dataset_released.return_value = {"matched": 1, "datasets": [DATASET]}

    def assertStatus(self, code, *args, **kwargs):
        with self.assertRaises(HTTPException) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.status_code, code)

    def test_writer_sets_flag_and_records_reviewer(self):
        response = call({"released": False, "released_by": "reviewer-a"})
        self.assertEqual(response.status_code, 200)
        self.db.set_dataset_released.assert_called_once_with("d-1", False, "reviewer-a")

    def test_released_by_defaults_to_token_user(self):
        call({"released": True})
        self.assertEqual(self.db.set_dataset_released.call_args.args[-1], "portal")

    def test_non_writer_is_forbidden(self):
        self.assertStatus(403, {"released": True}, user="hpc")
        self.assertStatus(403, {"released": True}, writers=())
        self.db.set_dataset_released.assert_not_called()

    def test_no_match_is_404(self):
        self.db.set_dataset_released.return_value = {"matched": 0, "datasets": []}
        self.assertStatus(404, {"released": True})

    def test_shared_uuid_is_409(self):
        self.db.set_dataset_released.return_value = {"matched": 2, "datasets": [DATASET, DATASET]}
        self.assertStatus(409, {"released": True})


class TestOutputDatasetUuid(unittest.TestCase):
    BASE = {"proc_type": "PGS", "input_dataset_paths": ["a"], "output_dataset_path": "b",
            "slurm_id": "1", "start_datetime": "2026-10-01T00:00:00"}

    def test_optional(self):
        self.assertIsNone(server.CreateProcessRequest(**self.BASE).output_dataset_uuid)

    def test_canonical_form(self):
        body = server.CreateProcessRequest(**self.BASE, output_dataset_uuid="0032B31B3A4558D280118953E2B941BA")
        self.assertEqual(body.output_dataset_uuid, "0032b31b-3a45-58d2-8011-8953e2b941ba")

    def test_rejects_non_uuid(self):
        with self.assertRaises(ValidationError):
            server.CreateProcessRequest(**self.BASE, output_dataset_uuid="not-a-uuid")


if __name__ == "__main__":
    unittest.main()
