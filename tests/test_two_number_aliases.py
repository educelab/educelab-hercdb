"""A two-number papyrus is found by either number (#45). Needs no Neo4j."""
import unittest

from educelab.hercdb.loader.graph_loader import PhercGraphDatabaseLoader as L


class TestPhercAliases(unittest.TestCase):

    def test_adds_both_numbers(self):
        self.assertEqual(L._pherc_aliases("1007/1673"), ["1007/1673", "1007", "1673"])
        self.assertEqual(L._pherc_aliases(" 152 / 157 "), ["152 / 157", "152", "157"])

    def test_other_papyri_unchanged(self):
        for name in ("1007", "118a", "PHerc. s.n. Cass LI", "Cass. 78 s.n. C"):
            self.assertEqual(L._pherc_aliases(name), L._expand_aliases(name), name)

    def test_a_pezzo_name_is_not_split(self):
        # Only PHerc names go through _pherc_aliases; pezzi keep _expand_aliases.
        self.assertEqual(L._expand_aliases("465/2"), ["465/2"])

    def test_no_duplicate_parts(self):
        self.assertEqual(L._pherc_aliases("1577/1579", "1577"), ["1577/1579", "1577", "1579"])


if __name__ == "__main__":
    unittest.main()
