"""The "archiving" Process status: accepted on write, never read as complete.

A stage whose output is published on the cluster but not yet confirmed on the
archive reports "archiving". Its scan must leave the work-list (the output
exists), while anything consuming that output must still wait for "completed".

Needs no Neo4j or server.
Run: uv run python -m unittest tests.test_archiving_status
"""
import asyncio
import unittest
from unittest import mock

from fastapi import HTTPException

from educelab import hercdb
from educelab.hercdb.db.connection import GraphDBConnection

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server


def status_of(*statuses):
    return GraphDBConnection._compute_pipeline_status(
        [{'stage': f'S{i}', 'status': s} for i, s in enumerate(statuses)])


class TestPipelineSummary(unittest.TestCase):

    def test_an_archiving_stage_summarizes_as_archiving(self):
        self.assertEqual(status_of('archiving'), 'archiving')

    def test_a_submitted_stage_still_reads_running(self):
        self.assertEqual(status_of('archiving', 'submitted'), 'running')

    def test_archiving_counts_as_done_beside_a_failure(self):
        self.assertEqual(status_of('archiving', 'failed'), 'partially_completed')

    def test_only_completed_is_completed(self):
        self.assertEqual(status_of('completed', 'archiving'), 'archiving')


class RecordingConnection(GraphDBConnection):
    def __init__(self):
        self.queries = []

    def _run_query(self, query, *args, **kwargs):
        self.queries.append(query)
        return [], None, None


class TestWorkList(unittest.TestCase):

    def test_an_archiving_process_takes_its_scan_off_the_work_list(self):
        db = RecordingConnection()
        db.find_unprocessed_datasets('PGS')
        self.assertIn('p.status IN ["completed", "archiving"]', db.queries[0])


def put_status(status):
    body = server.UpdateProcessStatusRequest(
        status=status, end_datetime="2026-10-07T12:00:00+00:00")
    return asyncio.run(server.update_process_status("uber-1", "PGS", body, user="hpc"))


class TestStatusEndpoint(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)
        self.db.update_process_status.side_effect = (
            lambda **kw: {"stage": kw["stage"], "status": kw["status"]})

    def test_archiving_is_accepted(self):
        self.assertEqual(put_status("Archiving").status_code, 200)
        self.assertEqual(self.db.update_process_status.call_args.kwargs["status"],
                         "archiving")

    def test_running_is_still_refused(self):
        with self.assertRaises(HTTPException) as caught:
            put_status("running")
        self.assertEqual(caught.exception.status_code, 400)
        self.db.update_process_status.assert_not_called()
