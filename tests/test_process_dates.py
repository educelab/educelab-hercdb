"""Unit tests for process status / end-time handling (issues #11 and #13).

Needs no Neo4j. Covers the REST boundary normalizing what a client posts to
`PUT /pipelines/{id}/processes/{proc_type}/status`, and the newest-dataset
reduction in `find_all_datasets_for_pherc` comparing end times as datetimes.

Run: uv run python -m unittest tests.test_process_dates
"""
import unittest
from datetime import datetime, timezone
from unittest import mock

from neo4j.time import DateTime
from pydantic import ValidationError

from educelab import hercdb
from educelab.hercdb.db.connection import GraphDBConnection, _as_datetime

# server.py connects at import; keep that off the network.
with mock.patch.object(hercdb, 'connect'):
    from educelab.hercdb.rest.server import UpdateProcessStatusRequest


class TestUpdateProcessStatusRequest(unittest.TestCase):

    def test_status_is_folded_to_lowercase(self):
        for sent in ('Completed', 'COMPLETED', ' completed '):
            with self.subTest(status=sent):
                body = UpdateProcessStatusRequest(status=sent, end_datetime='2026-06-01T10:30:00')
                self.assertEqual(body.status, 'completed')

    def test_end_datetime_is_stored_as_iso(self):
        cases = {
            '2026-06-01T10:30:00': '2026-06-01T10:30:00',
            '2026-06-01 10:30:00': '2026-06-01T10:30:00',
            '2026-06-01T10:30:00Z': '2026-06-01T10:30:00+00:00',
            '2026-06-01T10:30:00.519076+00:00': '2026-06-01T10:30:00.519076+00:00',
        }
        for sent, stored in cases.items():
            with self.subTest(end_datetime=sent):
                body = UpdateProcessStatusRequest(status='completed', end_datetime=sent)
                self.assertEqual(body.end_datetime, stored)

    def test_unparseable_end_datetime_is_rejected(self):
        for sent in ('', 'yesterday', '06/01/2026 10:30', '2026-13-01T00:00:00'):
            with self.subTest(end_datetime=sent):
                with self.assertRaises(ValidationError):
                    UpdateProcessStatusRequest(status='completed', end_datetime=sent)


class TestAsDatetime(unittest.TestCase):

    def test_neo4j_datetime(self):
        self.assertEqual(_as_datetime(DateTime(2022, 9, 8, 13, 42, 49, tzinfo=timezone.utc)),
                         datetime(2022, 9, 8, 13, 42, 49, tzinfo=timezone.utc))

    def test_naive_string_is_taken_as_utc(self):
        self.assertEqual(_as_datetime('2026-06-01 10:30:00'),
                         datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc))

    def test_missing_or_unparseable_is_none(self):
        for value in (None, '', 'yesterday', 42):
            with self.subTest(value=value):
                self.assertIsNone(_as_datetime(value))


class CannedConnection(GraphDBConnection):
    """Returns canned rows from `_run_query` instead of querying Neo4j."""

    def __init__(self, rows):
        self.rows = rows

    def _run_query(self, query, *args, **kwargs):
        return self.rows, None, None


def _processed_row(path, end_time, uuid='u1'):
    return {
        'uuid': uuid, 'pherc_name': '1', 'cornice_name': None, 'pezzo_name': None,
        'dataset': {'path': path}, 'dataset_type': 'PGSProcessed',
        'belongs_to_uuid': uuid, 'date_end': end_time,
        'pipeline_id': f'p-{path}', 'proc_status': 'completed',
    }


class TestNewestCompletedForPherc(unittest.TestCase):

    def _newest_path(self, rows):
        [artifact] = CannedConnection(rows).find_all_datasets_for_pherc('1', newest_completed=True)
        [ds] = artifact['datasets']
        return ds['path']

    def test_newest_by_instant_not_by_text(self):
        # As text, "2026-06-01T09:..." > "2026-06-01 11:...", since "T" > " ".
        rows = [_processed_row('earlier', '2026-06-01T09:00:00'),
                _processed_row('later', '2026-06-01 11:00:00+00:00')]
        self.assertEqual(self._newest_path(rows), 'later')

    def test_offsets_are_honoured(self):
        # 10:00-05:00 is 15:00 UTC, later than 12:00 UTC.
        rows = [_processed_row('utc-noon', '2026-06-01T12:00:00+00:00'),
                _processed_row('eastern', '2026-06-01T10:00:00-05:00')]
        self.assertEqual(self._newest_path(rows), 'eastern')

    def test_an_unparseable_end_time_never_wins(self):
        rows = [_processed_row('garbage', 'not a date'),
                _processed_row('dated', '2020-01-01T00:00:00')]
        self.assertEqual(self._newest_path(rows), 'dated')


if __name__ == '__main__':
    unittest.main()
