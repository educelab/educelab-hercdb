"""Reading the hand-kept extra scan links list (#43). Needs no Neo4j."""
import os
import tempfile
import unittest

from educelab.hercdb.loader.extra_scan_links import DEFAULT_PATH, load_links

HEADER = "label,scan_uuid,eid,note\n"


def write(text):
    fh = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
    fh.write(HEADER + text)
    fh.close()
    return fh.name


class TestLoadLinks(unittest.TestCase):

    def test_reads_rows(self):
        path = write("SpectralRaw, ce015560 ,c5ca1b3a,both trays\n")
        self.addCleanup(os.remove, path)
        self.assertEqual(load_links(path), [{'label': 'SpectralRaw', 'scan_uuid': 'ce015560', 'eid': 'c5ca1b3a'}])

    def test_rejects_a_bad_row(self):
        for row in ("FlatbedScanDataset,x,y,\n", "PGSRaw,,y,\n", "PGSRaw,x,,\n"):
            path = write(row)
            self.addCleanup(os.remove, path)
            with self.assertRaises(ValueError, msg=row):
                load_links(path)

    def test_the_shipped_list_reads(self):
        here = os.path.dirname(__file__)
        links = load_links(os.path.join(here, '..', DEFAULT_PATH))
        self.assertIn('ce015560-122b-46dc-a5cd-915191a3261d', {l['scan_uuid'] for l in links})


if __name__ == '__main__':
    unittest.main()
