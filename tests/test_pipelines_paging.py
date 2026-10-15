"""Server-side filter, sort and paging on GET /pipelines (#26).

The rules match the pipeline UI's in-process `_page()`, which this replaces.
Exercises the paging function on fixed rows and calls the handler with the DB
mocked out, so it needs no Neo4j or server.
"""
import asyncio
import json
import unittest
from unittest import mock

from educelab import hercdb
from educelab.hercdb.db.connection import PIPELINE_SORTS, _page_pipeline_summaries

with mock.patch.object(hercdb, "connect"), mock.patch.object(hercdb.config, "_load_config"):
    from educelab.hercdb.rest import server


def summary(pid, name='', start='', types=(), version=None, status='completed', uuid=''):
    return {'pipeline_id': pid, 'dataset_name': name, 'start_time': start, 'proc_types': list(types),
            'version': version, 'status': status, 'artifact_uuid': uuid}


ROWS = [
    summary('p1', 'PHerc6 Cornice 1', '2026-10-01T00:00:00', ['PGS', 'REG'], '2.2.0'),
    summary('p2', 'PHerc60', '2026-10-03T00:00:00', ['SPEC'], None, 'failed'),
    summary('p3', 'PHerc10', '2026-10-02T00:00:00', ['SPEC', 'REG', 'WEB'], '2.10.0', 'running', 'abc-uuid'),
    summary('p4', 'PHerc2', '2026-10-02T00:00:00', ['PGS'], '2.2.0'),
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
