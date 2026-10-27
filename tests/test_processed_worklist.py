"""Unit tests for the REG / WEB work-list (#66).

`find_unprocessed_datasets('REG' | 'WEB')` replaces acquisition-workflow's
client-side `worklist.candidates()`. These cover its selection rules on canned
query results, so they need no Neo4j: which artifacts are ready, which input
dataset is picked, and what a row carries.

Run: uv run python -m unittest tests.test_processed_worklist
"""
import unittest

from educelab.hercdb.db.connection import GraphDBConnection, _path_order_key


def identity(uuid, pherc, cornice=None, pezzo=None):
    return {'uuid': uuid, 'pherc_name': pherc, 'cornice_name': cornice, 'pezzo_name': pezzo}


def dataset(uuid, ds_type, path, complete=True, date_end=None):
    return {'uuid': uuid, 'ds_type': ds_type, 'path': path, 'complete': complete,
            'date_end': date_end}


class CannedConnection(GraphDBConnection):
    """Answers the work-list's three queries from canned rows, no driver."""

    def __init__(self, identities=(), datasets=(), attempts=()):
        self.answers = {'identity': list(identities), 'datasets': list(datasets),
                        'attempts': list(attempts)}
        self.params = {}

    def _run_query(self, query, **params):
        if 'ASSIGNED_TO]->(n)' in query:
            name = 'identity'
        elif ':OUTPUT]->(d)' in query:
            name = 'datasets'
        elif 'Process {stage: $stage}' in query:
            name = 'attempts'
        else:
            raise AssertionError(f'unexpected query: {query}')
        self.params[name] = params
        return self.answers[name], None, None


PGS = '/data/1044/pgs_20260901T100000'
SPEC = '/data/1044/spec_20260902T100000'


class TestRegReady(unittest.TestCase):

    def test_both_inputs_and_no_output_is_ready(self):
        db = CannedConnection(
            identities=[identity('u1', '1044', 'Cr 1')],
            datasets=[dataset('u1', 'PGSProcessed', PGS, date_end='2026-09-01T12:00:00'),
                      dataset('u1', 'SpectralProcessed', SPEC, date_end='2026-09-02T12:00:00')],
            attempts=[{'uuid': 'u1', 'attempts': 1, 'last_status': 'failed', 'last_notes': 'OOM'}])
        self.assertEqual(db.find_unprocessed_datasets('REG'), [{
            'uuid': 'u1', 'pherc': '1044', 'cornice': 'Cr 1', 'pezzo': None,
            'path': PGS, 'paths': {'pgs': PGS, 'spec': SPEC},
            'date_end': '2026-09-02T12:00:00',
            'attempts': 1, 'last_status': 'failed', 'last_notes': 'OOM',
        }])

    def test_never_tried_has_zero_attempts(self):
        db = CannedConnection(
            identities=[identity('u1', '1044')],
            datasets=[dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', SPEC)])
        row, = db.find_unprocessed_datasets('REG')
        self.assertEqual((row['attempts'], row['last_status'], row['last_notes'], row['date_end']),
                         (0, None, None, None))

    def test_usable_output_means_done(self):
        db = CannedConnection(
            identities=[identity('u1', '1044')],
            datasets=[dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', SPEC),
                      dataset('u1', 'Registered', '/data/1044/reg_1')])
        self.assertEqual(db.find_unprocessed_datasets('REG'), [])

    def test_unfinished_output_does_not_count_as_done(self):
        # Judged by a usable output, not by a Process: a stage that ran but
        # published nothing usable stays on the list.
        db = CannedConnection(
            identities=[identity('u1', '1044')],
            datasets=[dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', SPEC),
                      dataset('u1', 'Registered', '/data/1044/reg_1', complete=False)])
        self.assertEqual(len(db.find_unprocessed_datasets('REG')), 1)

    def test_missing_or_unusable_input_is_not_ready(self):
        for datasets in (
                [dataset('u1', 'PGSProcessed', PGS)],
                [dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', SPEC, complete=False)],
                [dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', None)]):
            with self.subTest(datasets=datasets):
                db = CannedConnection(identities=[identity('u1', '1044')], datasets=datasets)
                self.assertEqual(db.find_unprocessed_datasets('REG'), [])

    def test_no_pherc_is_skipped(self):
        db = CannedConnection(
            identities=[identity('u1', None)],
            datasets=[dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', SPEC)])
        self.assertEqual(db.find_unprocessed_datasets('REG'), [])

    def test_shared_uuid_reports_its_first_artifact(self):
        db = CannedConnection(
            identities=[identity('u1', '1044', 'Cr 1'), identity('u1', '1045', 'Cr 1')],
            datasets=[dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', SPEC)])
        row, = db.find_unprocessed_datasets('REG')
        self.assertEqual(row['pherc'], '1044')


class TestNewestInput(unittest.TestCase):

    def test_newest_usable_by_natural_path_order(self):
        db = CannedConnection(
            identities=[identity('u1', '1044')],
            datasets=[dataset('u1', 'PGSProcessed', '/d/pgs_9'),
                      dataset('u1', 'PGSProcessed', '/d/pgs_10'),
                      dataset('u1', 'PGSProcessed', '/d/pgs_11', complete=False),
                      dataset('u1', 'SpectralProcessed', SPEC)])
        row, = db.find_unprocessed_datasets('REG')
        self.assertEqual(row['paths']['pgs'], '/d/pgs_10')

    def test_path_order_key_is_natural(self):
        paths = ['/a/x_10', '/a/x_9', '/a/X_1', '/a/x_100']
        self.assertEqual(sorted(paths, key=_path_order_key), ['/a/X_1', '/a/x_9', '/a/x_10', '/a/x_100'])


class TestWeb(unittest.TestCase):

    def test_web_needs_the_registration_too(self):
        base = [dataset('u1', 'PGSProcessed', PGS), dataset('u1', 'SpectralProcessed', SPEC)]
        db = CannedConnection(identities=[identity('u1', '1044')], datasets=base)
        self.assertEqual(db.find_unprocessed_datasets('WEB'), [])

        db = CannedConnection(identities=[identity('u1', '1044')],
                              datasets=base + [dataset('u1', 'Registered', '/d/reg_1')])
        row, = db.find_unprocessed_datasets('WEB')
        self.assertEqual(row['paths'], {'pgs': PGS, 'spec': SPEC, 'reg': '/d/reg_1'})
        self.assertEqual(db.params['attempts'], {'stage': 'WEB'})
        self.assertEqual(db.params['datasets']['labels'],
                         ['PGSProcessed', 'Registered', 'SpectralProcessed', 'WebProcessed'])


class TestProcTypes(unittest.TestCase):

    def test_unknown_proc_type_lists_all_four(self):
        with self.assertRaises(ValueError) as caught:
            CannedConnection().find_unprocessed_datasets('BOGUS')
        self.assertIn('PGS, REG, SPEC, WEB', str(caught.exception))

    def test_nothing_is_ambiguous_for_reg_or_web(self):
        for proc_type in ('REG', 'WEB'):
            self.assertEqual(CannedConnection().find_ambiguous_datasets(proc_type), [])


if __name__ == '__main__':
    unittest.main()
