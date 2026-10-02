"""Integration tests for el-hercdb-exclude-test-scans (cli/exclude_test_scans.py).

Fixture: one throwaway PHerc with an EduceLabID, a real PGS scan, a *newer*
test PGS scan, and a real spectral scan. Three pipelines consume them:

    MIXED     PGS(test) + SPEC(real) -> REG -> WEB
    REG_ONLY  REG over MIXED's PGSProcessed + SpectralProcessed (cross-pipeline)
    PGS_ONLY  PGS(test)

So purging the test scan must delete MIXED's PGS/REG/WEB but keep its SPEC,
delete REG_ONLY and PGS_ONLY entirely (both end up with no Process), and report
MIXED's SpectralProcessed as needing re-registration.

Requires a live Neo4j connection -- run against dev, never prod. Everything
created here is removed in tearDownClass.
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from educelab import hercdb
from educelab.hercdb.cli import exclude_test_scans as ets

_STAMP = datetime.now().strftime('%Y%m%d%H%M%S')
PREFIX = f'TEST-EXCL-{_STAMP}'
EID = f'{PREFIX}-eid'
PHERC = f'{PREFIX}-pherc'

REAL_PGS = {'uuid': f'{PREFIX}-real-pgs', 'path': f'Dailies/{PREFIX}/real_pgs'}
TEST_PGS = {'uuid': f'{PREFIX}-test-pgs', 'path': f'Dailies/{PREFIX}/test_pgs'}
REAL_SPEC = {'uuid': f'{PREFIX}-real-spec', 'path': f'Dailies/Spectral/{PREFIX}/real_spec'}

MIXED = f'{PREFIX}-MIXED'
REG_ONLY = f'{PREFIX}-REGONLY'
PGS_ONLY = f'{PREFIX}-PGSONLY'
PIPELINES = (MIXED, REG_ONLY, PGS_ONLY)

OUT = f'/test/excl/{_STAMP}'
MIXED_PGS = f'{OUT}/mixed_pgs'
MIXED_SPEC = f'{OUT}/mixed_spec'
MIXED_REG = f'{OUT}/mixed_reg'
MIXED_WEB = f'{OUT}/mixed_web'
REGONLY_REG = f'{OUT}/regonly_reg'
PGSONLY_PGS = f'{OUT}/pgsonly_pgs'

EXPECTED_MANIFEST = {
    ('PGSProcessed', MIXED_PGS),
    ('Registered', MIXED_REG),
    ('WebProcessed', MIXED_WEB),
    ('Registered', REGONLY_REG),
    ('PGSProcessed', PGSONLY_PGS),
}

SCANS = [{'label': 'PGSRaw', 'uuid': TEST_PGS['uuid'], 'path': TEST_PGS['path'],
          'eid': EID, 'category': 'res_test'}]

NOW = datetime.now(timezone.utc)


class TestExcludeTestScans(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        assert cls.db.verify_connection(), 'no Neo4j connection'
        cls.driver = cls.db.driver
        print(f'\nexclude_test_scans fixture on {cls.db.uri}')

        cls.db._run_query("""
            CREATE (ph:PHerc {displayName: $pherc, aliases: [$pherc]})
            CREATE (e:EduceLabID {uuid: $eid})-[:ASSIGNED_TO]->(ph)
            CREATE (:PGSRaw {uuid: $real_pgs.uuid, path: $real_pgs.path,
                             complete: 'True', date_end: $older})-[:BELONGS_TO]->(e)
            CREATE (:PGSRaw {uuid: $test_pgs.uuid, path: $test_pgs.path,
                             complete: 'True', date_end: $newer})-[:BELONGS_TO]->(e)
            CREATE (:SpectralRaw {uuid: $real_spec.uuid, path: $real_spec.path,
                                  complete: 'True', date_end: $older})-[:BELONGS_TO]->(e)
            """, pherc=PHERC, eid=EID, real_pgs=REAL_PGS, test_pgs=TEST_PGS,
            real_spec=REAL_SPEC, older=NOW - timedelta(days=30), newer=NOW)

        t = NOW.isoformat()
        for pid in PIPELINES:
            cls.db.initialize_pipeline(pid, EID, t)
        stages = [
            (MIXED, 'PGS', [TEST_PGS['path']], MIXED_PGS, '1'),
            (MIXED, 'SPEC', [REAL_SPEC['path']], MIXED_SPEC, '2'),
            (MIXED, 'REG', [MIXED_PGS, MIXED_SPEC], MIXED_REG, '3'),
            (MIXED, 'WEB', [MIXED_REG], MIXED_WEB, '4'),
            (REG_ONLY, 'REG', [MIXED_PGS, MIXED_SPEC], REGONLY_REG, '5'),
            (PGS_ONLY, 'PGS', [TEST_PGS['path']], PGSONLY_PGS, '6'),
        ]
        for pid, stage, inputs, output, slurm in stages:
            assert cls.db.initialize_process(pid, stage, inputs, output, slurm, t), \
                f'fixture: {pid} {stage} was not recorded'

        # Everything is still "submitted" here, which is what in_flight guards.
        cls.in_flight_before = ets.in_flight(cls.driver, SCANS)

        for pid, stage, *_ in stages:
            cls.db.update_process_status(pid, stage, 'completed', t)

    @classmethod
    def tearDownClass(cls):
        cls.db._run_query("""
            MATCH (pl:Pipeline) WHERE pl.pipeline_id IN $pids
            OPTIONAL MATCH (pl)<-[:STAGE_OF]-(proc:Process)
            OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
            DETACH DELETE out, proc, pl
            """, pids=list(PIPELINES))
        cls.db._run_query("""
            MATCH (n) WHERE (n:PGSProcessed OR n:SpectralProcessed
                             OR n:Registered OR n:WebProcessed)
                        AND n.path STARTS WITH $out
            DETACH DELETE n
            """, out=OUT)
        cls.db._run_query("""
            MATCH (n) WHERE (n:PGSRaw OR n:SpectralRaw) AND n.uuid STARTS WITH $prefix
            DETACH DELETE n
            """, prefix=PREFIX)
        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $eid}) OPTIONAL MATCH (e)-[:ASSIGNED_TO]->(ph)
            DETACH DELETE e, ph
            """, eid=EID)

    def _pgs_work_for_fixture(self):
        return [r for r in self.db.find_unprocessed_datasets('PGS') if r['uuid'] == EID]

    def _manifest(self):
        return {(r['label'], r['path']) for r in ets.downstream_datasets(self.driver, SCANS)}

    def test_full_sequence(self):
        # --- report, before anything changes --------------------------------
        self.assertTrue(self.in_flight_before, 'submitted stages should block writes')
        self.assertEqual(ets.in_flight(self.driver, SCANS), [])

        [row] = ets.validate(self.driver, SCANS)
        self.assertEqual(row['problem'], '')
        self.assertEqual(row['state'], 'attached')

        # The bug being fixed: the newest scan is the test scan, it is
        # processed, so the dispatcher considers the artifact done.
        self.assertEqual(self._pgs_work_for_fixture(), [])

        self.assertEqual(self._manifest(), EXPECTED_MANIFEST)

        [affected] = ets._read(self.driver, ets.AFFECTED_QUERY, scans=SCANS)
        self.assertEqual((affected['artifact_type'], affected['pherc'],
                          affected['cornice'], affected['pezzo']),
                         ('PHerc', PHERC, None, None))

        mixed ={r['pipeline_id']: r for r in
                 ets._read(self.driver, ets.MIXED_PIPELINES_QUERY, scans=SCANS)}
        self.assertEqual(set(mixed), {MIXED})
        self.assertEqual(mixed[MIXED]['surviving_stages'], ['SPEC'])

        reprocess = ets._read(self.driver, ets.NEEDS_REPROCESSING_QUERY, scans=SCANS)
        self.assertEqual({(r['label'], r['path']) for r in reprocess},
                         {('SpectralProcessed', MIXED_SPEC)})

        # A drifted CSV row is flagged, not silently skipped.
        drifted = [dict(SCANS[0], path='Dailies/elsewhere')]
        self.assertEqual(ets.validate(self.driver, drifted)[0]['problem'], 'path differs')

        # --- detach ---------------------------------------------------------
        self.assertEqual(ets.detach(self.driver, drifted)['detached'], 0)
        result = ets.detach(self.driver, SCANS)
        self.assertEqual(result, {'detached': 1, 'edges_removed': 1})
        self.assertEqual(ets.detach(self.driver, SCANS)['detached'], 0)  # idempotent

        [row] = ets.validate(self.driver, SCANS)
        self.assertEqual((row['problem'], row['state'], row['excluded']),
                         ('', 'floating', True))
        records, _, _ = self.db._run_query(
            "MATCH (d:PGSRaw {uuid: $u}) RETURN d.detached_from_eid AS eids, "
            "d.excluded_reason AS reason", u=TEST_PGS['uuid'])
        self.assertEqual((records[0]['eids'], records[0]['reason']), ([EID], 'res_test'))

        # The real scan is now the newest PGS scan, and unprocessed.
        self.assertEqual([r['path'] for r in self._pgs_work_for_fixture()],
                         [REAL_PGS['path']])

        # INPUT edges survive the detach, so the closure is unchanged.
        self.assertEqual(self._manifest(), EXPECTED_MANIFEST)

        # --- purge ----------------------------------------------------------
        stale = EXPECTED_MANIFEST - {('WebProcessed', MIXED_WEB)}
        with self.assertRaises(ets.ManifestMismatch):
            ets.purge(self.driver, SCANS, stale)
        self.assertEqual(self._manifest(), EXPECTED_MANIFEST, 'rollback failed')

        result = ets.purge(self.driver, SCANS, EXPECTED_MANIFEST)
        self.assertEqual(result['datasets'], 5)
        self.assertEqual(result['processes'], 5)
        self.assertEqual(set(result['pipelines']), {REG_ONLY, PGS_ONLY})

        self.assertEqual(self._manifest(), set())
        records, _, _ = self.db._run_query("""
            MATCH (pl:Pipeline) WHERE pl.pipeline_id IN $pids
            OPTIONAL MATCH (pl)<-[:STAGE_OF]-(p:Process)-[:OUTPUT]->(o)
            RETURN pl.pipeline_id AS pid, collect(p.stage) AS stages,
                   collect(o.path) AS outputs
            """, pids=list(PIPELINES))
        self.assertEqual([(r['pid'], r['stages'], r['outputs']) for r in records],
                         [(MIXED, ['SPEC'], [MIXED_SPEC])])

        records, _, _ = self.db._run_query(
            "MATCH (d:PGSRaw {uuid: $u}) RETURN COUNT { (d)--() } AS degree",
            u=TEST_PGS['uuid'])
        self.assertEqual(records[0]['degree'], 0, 'test scan should be fully floating')

        # Nothing left to purge.
        self.assertEqual(ets.purge(self.driver, SCANS, set()),
                         {'processes': 0, 'datasets': 0, 'pipelines': []})


class TestLoadExclusions(unittest.TestCase):
    def test_dedupes_and_rejects_bad_labels(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'x.csv')
            with open(path, 'w') as fh:
                fh.write('category,label,ds_uuid,path,complete,eid,atype,aname\n'
                         'test,PGSRaw,u1,p1,True,e1,,\n'
                         'test,PGSRaw,u1,p1,True,e1,,\n'
                         'test,SpectralRaw,u1,p2,True,e1,,\n')
            self.assertEqual(len(ets.load_exclusions(path)), 2)
            with open(path, 'a') as fh:
                fh.write('test,PGSProcessed,u2,p3,True,e1,,\n')
            with self.assertRaises(ValueError):
                ets.load_exclusions(path)

    @unittest.skipUnless(os.path.exists(ets.DEFAULT_CSV), 'local input_data only')
    def test_real_list(self):
        scans = ets.load_exclusions('input_data/excluded_test_scans.csv')
        self.assertEqual(len(scans), 83)


if __name__ == '__main__':
    unittest.main()
