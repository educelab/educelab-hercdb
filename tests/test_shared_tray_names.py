"""Which uuid-sheet names belong to which node on a shared tray (#61).

Pure functions, so these need no Neo4j or server.
"""
import unittest

from educelab.hercdb.loader.graph_loader import names_papyrus, same_number


class TestNamesPapyrus(unittest.TestCase):

    def test_a_list_of_papyri_names_none_of_them(self):
        for sheet, own in (("924-935", "924"), ("924-935", "935"), ("1157-1191", "1191"),
                           ("603, 610, 636", "610"), ("1691-1208", "1208")):
            self.assertFalse(names_papyrus(sheet, own), (sheet, own))

    def test_another_papyrus_name(self):
        self.assertFalse(names_papyrus("4 PHerc. s.n.", "1832"))
        self.assertFalse(names_papyrus("s.n. I-III Cass CXIV", "1829"))

    def test_forms_of_its_own_name(self):
        for sheet, own in (("1157", "1157"), ("4 PHerc. s.n.", "4 PHerc. s.n."),
                           ("s.n. I-III Cass CXIV", "PHerc. s.n. I-III Cass CXIV"),
                           ("s.n. Cass. LVIII", "PHerc. s.n. Cass. LVIII"),
                           ("PHerc 1157", "1157")):
            self.assertTrue(names_papyrus(sheet, own), (sheet, own))

    def test_a_suffixed_number_is_another_papyrus(self):
        for sheet, own in (("118a", "118"), ("927bis", "927"), ("1157-1191 A", "1157")):
            self.assertFalse(names_papyrus(sheet, own), (sheet, own))

    def test_a_typo_is_not_its_name(self):
        # Q-20: the uuid sheet's CXIV against the metadata's XCIV.
        self.assertFalse(names_papyrus("s.n. IV Cass CXIV", "PHerc. s.n. IV Cass XCIV"))

    def test_blank(self):
        self.assertFalse(names_papyrus("", "924"))
        self.assertFalse(names_papyrus("924", None))


class TestSameNumber(unittest.TestCase):

    def test_spellings_of_its_own_cornice(self):
        for sheet, own in (("1 (Oslo)", "1 (Osloense)"), ("2 (oslo)", "2 (Osloense)"),
                           ("465-II", "465/2"), ("1 (Fackelmann)", "1 (Fackelmann)")):
            self.assertTrue(same_number(sheet, own), (sheet, own))

    def test_another_cornice_number(self):
        self.assertFalse(same_number("2 (oslo)", "1 (Osloense)"))

    def test_no_number_contradicts_nothing(self):
        self.assertTrue(same_number("Oslo", "1 (Osloense)"))
        self.assertTrue(same_number("2", "Scorze da 90 a 223"))


if __name__ == "__main__":
    unittest.main()
