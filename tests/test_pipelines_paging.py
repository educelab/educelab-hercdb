"""Server-side filter, sort and paging on GET /pipelines (#26), and the label
it searches and sorts on (#80).

The rules match the pipeline UI's in-process `_page()`, which this replaces.
Exercises the paging function on fixed rows and calls the handler with the DB
mocked out, so it needs no Neo4j or server.
"""
import asyncio
import json
import unittest
from unittest import mock

from educelab import hercdb
from educelab.hercdb.db.connection import PIPELINE_SORTS, GraphDBConnection, _page_pipeline_summaries

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server


def summary(pid, name='', start='', types=(), version=None, status='completed', uuid='', label=None):
    return {'pipeline_id': pid, 'dataset_name': name, 'label': label, 'start_time': start,
            'proc_types': list(types), 'version': version, 'status': status, 'artifact_uuid': uuid}


ROWS = [
    summary('p1', 'PHerc6 Cornice 1', '2026-10-01T00:00:00', ['PGS', 'REG'], '2.2.0',
            label='PHerc. 6, Cornice 1'),
    summary('p2', 'PHerc60', '2026-10-03T00:00:00', ['SPEC'], None, 'failed', label='PHerc. 60'),
    summary('p3', 'PHerc10', '2026-10-02T00:00:00', ['SPEC', 'REG', 'WEB'], '2.10.0', 'running', 'abc-uuid',
            label='PHerc. 10'),
    summary('p4', 'PHerc2', '2026-10-02T00:00:00', ['PGS'], '2.2.0', label='PHerc. 2'),
]

# Where the label and dataset_name disagree on order (#80): by dataset_name,
# "PHerctavoletta" sorts before "PHerc90"; by label, "PHerc. 90" comes first.
LABELLED = [
    summary('t1', 'PHerctavoletta Cornice Cass. 38 (A)', label='Tavoletta A, Cassetto 38'),
    summary('t2', 'PHerc90 Cornice Scorze da 90 a 223', label='PHerc. 90, Scorze da 90 a 223'),
    summary('t3', 'PHercCass. 78 s.n. C Cornice Cass. 78', label='Cassetto 78 s.n. C'),
    summary('t4'),  # no artifact
]


def page(search=None, sort='started', direction=None, offset=0, limit=None):
    return _page_pipeline_summaries(ROWS, search, sort, direction, offset, limit)


def ids(result):
    return [r['pipeline_id'] for r in result['rows']]


class TestPagePipelineSummaries(unittest.TestCase):

    def test_default_is_newest_first_ties_on_id(self):
        result = page()
        # p3 and p4 share a start time; desc reverses the pipeline_id tie-break too.
        self.assertEqual(ids(result), ['p2', 'p4', 'p3', 'p1'])
        self.assertEqual((result['matched'], result['total'], result['sort'], result['dir']),
                         (4, 4, 'started', 'desc'))

    def test_offset_and_limit(self):
        self.assertEqual(ids(page(offset=1, limit=2)), ['p4', 'p3'])
        self.assertEqual(ids(page(offset=3, limit=10)), ['p1'])
        self.assertEqual(page(offset=9, limit=2)['rows'], [])

    def test_search_folds_words(self):
        for search in ('pherc 6', 'PHerc. 6', 'PHERC6'):
            with self.subTest(search=search):
                self.assertEqual(sorted(ids(page(search))), ['p1', 'p2'])

    def test_search_ending_in_punctuation_ends_on_a_word(self):
        result = page('PHerc. 6,')
        self.assertEqual(ids(result), ['p1'])
        self.assertEqual((result['matched'], result['total']), (1, 4))

    def test_search_fields(self):
        cases = {'abc-uuid': ['p3'], 'web': ['p3'], '2.10': ['p3'], 'failed': ['p2'], 'p4': ['p4'],
                 'pgs reg': ['p1']}
        for search, expected in cases.items():
            with self.subTest(search=search):
                self.assertEqual(ids(page(search)), expected)

    def test_punctuation_only_search_matches_all(self):
        self.assertEqual(page('..')['matched'], 4)

    def test_sorts(self):
        self.assertEqual(ids(page(sort='artifact')), ['p4', 'p1', 'p3', 'p2'])  # natural order
        self.assertEqual(ids(page(sort='version')), ['p3', 'p4', 'p1', 'p2'])   # unversioned last
        self.assertEqual(ids(page(sort='version', direction='asc')), ['p2', 'p1', 'p4', 'p3'])
        self.assertEqual(ids(page(sort='status')), ['p1', 'p4', 'p2', 'p3'])
        self.assertEqual(ids(page(sort='type')), ['p4', 'p1', 'p2', 'p3'])

    def test_unknown_sort_or_direction_raises(self):
        with self.assertRaises(ValueError):
            page(sort='nope')
        with self.assertRaises(ValueError):
            page(direction='up')


class TestLabel(unittest.TestCase):
    """Search and the artifact sort run over the label the UI shows (#80)."""

    def labelled(self, search=None, sort='started', direction=None):
        return ids(_page_pipeline_summaries(LABELLED, search, sort, direction, 0, None))

    def test_search_matches_the_label(self):
        cases = {'Tavoletta A, Cassetto 38': ['t1'], 'PHerc. 90, Scorze': ['t2'],
                 'cassetto 78 s.n.': ['t3'], 'Cassetto': ['t1', 't3']}
        for search, expected in cases.items():
            with self.subTest(search=search):
                self.assertEqual(sorted(self.labelled(search)), expected)

    def test_search_still_matches_dataset_name(self):
        self.assertEqual(self.labelled('PHerc90 Cornice Scorze'), ['t2'])
        self.assertEqual(self.labelled('pherctavoletta'), ['t1'])

    def test_artifact_sort_is_by_label(self):
        # No label sorts first ascending, as an empty dataset_name did.
        self.assertEqual(self.labelled(sort='artifact'), ['t4', 't3', 't2', 't1'])
        self.assertEqual(self.labelled(sort='artifact', direction='desc'), ['t1', 't2', 't3', 't4'])


class SummaryConnection(GraphDBConnection):
    """Feeds get_all_pipeline_summaries canned pipelines, stages and names."""

    def __init__(self, pipelines, names):
        self.pipelines, self.names = pipelines, names

    def find_pipelines(self):
        return [{'pipeline_id': pid, 'artifact_uuid': uuid, 'version': None}
                for pid, uuid in self.pipelines.items()]

    def _all_pipeline_processes(self):
        return {pid: [{'stage': 'PGS', 'status': 'completed', 'start_time': '2026-10-01T00:00:00'}]
                for pid in self.pipelines}

    def find_artifact_names_by_uuids(self, uuids):
        return {u: n for u, n in self.names.items() if u in uuids}


class TestSummaryLabel(unittest.TestCase):

    def test_rows_carry_the_artifact_label(self):
        db = SummaryConnection(
            {'a': 'u90', 'b': 'u90', 'c': 'utav', 'd': 'unassigned', 'e': None},
            {'u90': {'pherc': '90', 'cornice': 'Scorze da 90 a 223', 'pezzo': None},
             'utav': {'pherc': 'tavoletta', 'cornice': 'Cass. 38 (A)', 'pezzo': None}})
        rows = {r['pipeline_id']: r for r in db.get_all_pipeline_summaries()}
        self.assertEqual(
            {pid: (r['dataset_name'], r['label'], r['label_parts']) for pid, r in rows.items()},
            {'a': ('PHerc90 Cornice Scorze da 90 a 223', 'PHerc. 90, Scorze da 90 a 223',
                   ['PHerc. 90', 'Scorze da 90 a 223']),
             'b': ('PHerc90 Cornice Scorze da 90 a 223', 'PHerc. 90, Scorze da 90 a 223',
                   ['PHerc. 90', 'Scorze da 90 a 223']),
             'c': ('PHerctavoletta Cornice Cass. 38 (A)', 'Tavoletta A, Cassetto 38',
                   ['Tavoletta A', 'Cassetto 38']),
             'd': ('', None, []),
             'e': ('', None, [])})
        self.assertIsNot(rows['a']['label_parts'], rows['b']['label_parts'])


class TestPipelinesRoute(unittest.TestCase):

    def setUp(self):
        self.db = mock.patch.object(server, "db").start()
        self.addCleanup(mock.patch.stopall)
        self.db.get_all_pipeline_summaries.return_value = ROWS
        self.db.get_pipeline_summaries_page.side_effect = (
            lambda **kw: _page_pipeline_summaries(ROWS, kw['search'], kw['sort'], kw['direction'],
                                                  kw['offset'], kw['limit']))

    def call(self, **params):
        params = {"search": None, "sort": None, "direction": None, "offset": None, "limit": None, **params}
        return json.loads(asyncio.run(server.get_pipelines(**params, user="t")).body)

    def test_no_params_is_the_bare_list(self):
        self.assertEqual(self.call(), ROWS)
        self.db.get_pipeline_summaries_page.assert_not_called()

    def test_any_param_pages(self):
        for params in ({"limit": 2}, {"search": "pherc"}, {"sort": "status"}, {"direction": "asc"},
                       {"offset": 0}):
            with self.subTest(**params):
                self.assertEqual(set(self.call(**params)), {"rows", "matched", "total", "sort", "dir"})

    def test_route_accepts_exactly_the_db_sorts(self):
        params = {p['name']: p['schema']['anyOf'][0]
                  for p in server.app.openapi()['paths']['/pipelines']['get']['parameters']}
        self.assertEqual(params['sort']['enum'], list(PIPELINE_SORTS))
        self.assertEqual(params['dir']['enum'], ['asc', 'desc'])

    def test_defaults_when_paging(self):
        self.call(limit=2)
        self.db.get_pipeline_summaries_page.assert_called_with(
            search=None, sort="started", direction=None, offset=0, limit=2)


if __name__ == "__main__":
    unittest.main()
