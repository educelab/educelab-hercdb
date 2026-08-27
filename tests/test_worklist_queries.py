"""Unit tests for the parameterized work-list queries.

Most of this suite needs live Neo4j; these do not. They cover the part of
`find_unprocessed_datasets` / `find_ambiguous_datasets` that is pure logic:
which node label and Process stage a proc_type resolves to, and that an unknown
one is refused before any query runs. Neo4j cannot parameterize a node label, so
that lookup is what keeps the interpolation safe.

Run: uv run python -m unittest tests.test_worklist_queries
"""
import unittest
from unittest import mock

from educelab.hercdb.db.connection import GraphDBConnection, _CANDIDATE_LABELS


class RecordingConnection(GraphDBConnection):
    """Records the Cypher it is asked to run instead of running it.

    Overrides `__init__` so no driver is created; `close()` guards on the class
    attribute `driver = None`, so teardown stays safe.
    """

    def __init__(self):
        self.queries = []

    def _run_query(self, query, *args, **kwargs):
        self.queries.append(query)
        return [], None, None


class TestCandidateLabels(unittest.TestCase):

    def test_spec_scans_spectral_raw(self):
        db = RecordingConnection()
        self.assertEqual(db.find_unprocessed_datasets('SPEC'), [])
        query = db.queries[0]
        self.assertIn('MATCH (d:SpectralRaw)', query)
        self.assertIn('Process {stage: "SPEC"}', query)

    def test_pgs_scans_pgs_raw(self):
        db = RecordingConnection()
        self.assertEqual(db.find_unprocessed_datasets('PGS'), [])
        query = db.queries[0]
        self.assertIn('MATCH (d:PGSRaw)', query)
        self.assertIn('Process {stage: "PGS"}', query)

    def test_the_ambiguous_query_is_parameterized_too(self):
        db = RecordingConnection()
        self.assertEqual(db.find_ambiguous_datasets('PGS'), [])
        self.assertIn('MATCH (d:PGSRaw)', db.queries[0])

    def test_an_unknown_proc_type_runs_no_query(self):
        # The REST layer turns this ValueError into a 400. It must be raised
        # before anything reaches the database.
        db = RecordingConnection()
        for bad in ('REG', 'WEB', '', 'SpectralRaw', 'PGS) RETURN 1 //'):
            with self.subTest(proc_type=bad):
                with self.assertRaises(ValueError):
                    db.find_unprocessed_datasets(bad)
                with self.assertRaises(ValueError):
                    db.find_ambiguous_datasets(bad)
        self.assertEqual(db.queries, [])

    def test_the_db_layer_is_case_sensitive(self):
        # Deliberate: only the REST layer forgives case, so a lower-case
        # proc_type reaching here means a caller passed something unexpected.
        db = RecordingConnection()
        with self.assertRaises(ValueError):
            db.find_unprocessed_datasets('pgs')

    def test_the_error_names_what_is_supported(self):
        db = RecordingConnection()
        with self.assertRaises(ValueError) as caught:
            db.find_unprocessed_datasets('REG')
        message = str(caught.exception)
        for proc_type in _CANDIDATE_LABELS:
            self.assertIn(proc_type, message)

    def test_only_dict_values_reach_the_query(self):
        # The injection guarantee: every label the query can interpolate comes
        # from this dict, so no caller-supplied string is ever interpolated.
        db = RecordingConnection()
        for proc_type, label in _CANDIDATE_LABELS.items():
            db.queries.clear()
            db.find_unprocessed_datasets(proc_type)
            self.assertIn(f'MATCH (d:{label})', db.queries[0])


class TestSpectralAliases(unittest.TestCase):
    """0.3.2's names stay, so nothing has to change in the same release."""

    def test_unprocessed_alias_asks_for_spec(self):
        db = RecordingConnection()
        self.assertEqual(db.find_unprocessed_spectral_datasets(), [])
        self.assertIn('MATCH (d:SpectralRaw)', db.queries[0])

    def test_ambiguous_alias_asks_for_spec(self):
        db = RecordingConnection()
        self.assertEqual(db.find_ambiguous_spectral_datasets(), [])
        self.assertIn('MATCH (d:SpectralRaw)', db.queries[0])


class TestRouteOrdering(unittest.TestCase):
    """FastAPI matches routes in declaration order.

    If the parameterized pair were declared first, `/datasets/spectral/...`
    would bind proc_type='spectral' and every 0.3.2 client would get a 400.
    """

    def test_the_literal_spectral_routes_are_declared_first(self):
        with mock.patch('educelab.hercdb.connect',
                        return_value=mock.MagicMock()):
            from educelab.hercdb.rest import server

        paths = [route.path for route in server.app.routes]
        for suffix in ('unprocessed', 'ambiguous'):
            with self.subTest(suffix=suffix):
                self.assertLess(paths.index(f'/datasets/spectral/{suffix}'),
                                paths.index(f'/datasets/{{proc_type}}/{suffix}'))


if __name__ == '__main__':
    unittest.main()
