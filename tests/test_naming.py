"""Object kind, method and label from artifact names (#23).

Pure functions, so these need no Neo4j or server. The cases are name shapes
seen on the graph; the counts in comments are from dev on 2026-10-22.
"""
import unittest

from educelab.hercdb import naming
from educelab.hercdb.naming import describe, is_papyrus, label, label_parts, method, object_kind, tidy


class TestKind(unittest.TestCase):

    def test_papyrus_node(self):
        for pherc in ("90", "118a", "1007/1673", "Joannowsky Papyrus", "PHerc. s.n. Cass LI",
                      "Cass. 78 s.n. C", "cass.75 s. n. B", "TH A 74"):
            self.assertEqual(object_kind(pherc), naming.PAPYRUS, pherc)

    def test_placeholder_and_loose_material_are_not_objects(self):
        for pherc in ("tavoletta", "Cassetto", "frammenti", "folded sheet",
                      "frammento di papiro ercolanese", "s.n. frammenti 1-2"):
            self.assertIsNone(object_kind(pherc), pherc)
            self.assertFalse(is_papyrus(pherc), pherc)

    def test_cornice(self):
        for cornice in ("1", "12 (Osloense)", "1 (Fackelmann)", "IV", "side A + side B",
                        "cornice lunga", "2 (pz 3)"):
            self.assertEqual(object_kind("421", cornice), naming.CORNICE, cornice)

    def test_scorza(self):
        for cornice in ("Scorze da 90 a 223", "Scorze 1115-1572", "Scorze 1820-1821-1083bis-Cass.92 s.n. A"):
            self.assertEqual(object_kind("90", cornice), naming.SCORZA, cornice)

    def test_pezzo(self):
        self.assertEqual(object_kind("118a", None, "3"), naming.PEZZO)
        self.assertEqual(object_kind("465", "1 (Fackelmann)", "2"), naming.PEZZO)
        self.assertEqual(object_kind("76", "5", "Left"), naming.PEZZO)

    def test_cassetto_piece(self):
        for pherc, cornice in (("571", "Cass. 31"), ("1362", "Cass.75"), ("1105", "cass. 116"),
                               ("Cass. 78 s.n. C", "Cass.78 s.n. da A a F"),
                               ("1114", "Cass.78 s.n. A-B (1114?; C,D,E,F)"), ("72", "pz in Cass.7")):
            self.assertEqual(object_kind(pherc, cornice), naming.CASSETTO_PIECE, (pherc, cornice))

    def test_whole_cassetto(self):
        # Assumption Q-09: everything under the "Cassetto" placeholder.
        for cornice in ("Cass. 51 (A)", "Cass. 52 (B)", "Cass. 98"):
            self.assertEqual(object_kind("Cassetto", cornice), naming.WHOLE_CASSETTO, cornice)

    def test_tavoletta(self):
        for cornice in ("Cass. 38 (A)", "Cass.29 (B)", "Cass. 113", "Cass. 38 (removed fragments)"):
            self.assertEqual(object_kind("tavoletta", cornice), naming.TAVOLETTA, cornice)

    def test_frammenti(self):
        for pherc, cornice in (("frammenti", "Cass.1"), ("folded sheet", "Cass. 116"),
                               ("s.n. frammenti 1-2", "Cass.107")):
            self.assertEqual(object_kind(pherc, cornice), naming.FRAMMENTI, pherc)

    def test_no_name(self):
        self.assertIsNone(object_kind(None))
        self.assertIsNone(object_kind(""))
        # A cornice whose name tidies away (one is named ".") is still a cornice.
        self.assertEqual(object_kind("421", "."), naming.CORNICE)
        self.assertEqual(label_parts("421", "."), ["PHerc. 421"])


class TestMethod(unittest.TestCase):

    def test_methods(self):
        cases = {
            "1 (Osloense)": "Osloense",
            "10 Osloense)": "Osloense",  # typo seen live
            "3 Osloense": "Osloense",
            "1 (Oslo)": "Osloense",  # Assumption Q-04
            "1 (Fackelmann)": "Fackelmann",
            "1": None,
            "Scorze da 90 a 223": None,
            "Cass. 51 (A)": None,
            None: None,
        }
        for cornice, expected in cases.items():
            self.assertEqual(method(cornice), expected, cornice)

    def test_pezzo_takes_its_cornice_method(self):
        self.assertEqual(describe("465", "1 (Fackelmann)", "2")["method"], "Fackelmann")


class TestLabel(unittest.TestCase):

    def test_labels(self):
        cases = [
            (("90",), ["PHerc. 90"]),
            (("90", "Scorze da 90 a 223"), ["PHerc. 90", "Scorze da 90 a 223"]),
            (("421", "2"), ["PHerc. 421", "Cornice 2"]),
            (("Joannowsky Papyrus", "IV"), ["Joannowsky Papyrus", "Cornice IV"]),
            (("465", "1 (Fackelmann)", "2"), ["PHerc. 465", "Cornice 1 (Fackelmann)", "Pezzo 2"]),
            (("21", "10 Osloense)"), ["PHerc. 21", "Cornice 10 (Osloense)"]),
            (("571", "Cass. 31"), ["PHerc. 571", "Cassetto 31"]),
            (("tavoletta", "Cass. 38 (A)"), ["Tavoletta A", "Cassetto 38"]),
            (("tavoletta", "Cass.106"), ["Tavoletta", "Cassetto 106"]),
            (("frammenti", "Cass.1"), ["Frammenti", "Cassetto 1"]),
            (("Cass. 78 s.n. C", "Cass.78 s.n. da A a F"), ["Cassetto 78 s.n. C"]),
            (("PHerc. s.n. Cass LI", "1 (Osloense)"), ["PHerc. s.n. Cass LI", "Cornice 1 (Osloense)"]),
            # Assumption Q-10: a whole cassetto is labelled by itself.
            (("Cassetto", "Cass. 51 (A)"), ["Cassetto 51 (A)"]),
            (("Cassetto", "Cass. 98"), ["Cassetto 98"]),
        ]
        for names, expected in cases:
            self.assertEqual(label_parts(*names), expected, names)
            self.assertEqual(label(*names), ", ".join(expected), names)

    def test_empty(self):
        self.assertEqual(label_parts(None), [])
        self.assertIsNone(label(None))


class TestTidy(unittest.TestCase):

    def test_tidy(self):
        self.assertEqual(tidy("Cass.106"), "Cass. 106")
        self.assertEqual(tidy("cass. 75 s. n. B"), "cass. 75 s.n. B")
        self.assertEqual(tidy("10 Osloense)"), "10 (Osloense)")
        self.assertIsNone(tidy("."))
        self.assertIsNone(tidy("  "))


class TestDescribe(unittest.TestCase):

    def test_shape(self):
        self.assertEqual(describe("421", "1 (Osloense)"), {
            "kind": "cornice",
            "method": "Osloense",
            "label": "PHerc. 421, Cornice 1 (Osloense)",
            "label_parts": ["PHerc. 421", "Cornice 1 (Osloense)"],
        })


if __name__ == "__main__":
    unittest.main()
