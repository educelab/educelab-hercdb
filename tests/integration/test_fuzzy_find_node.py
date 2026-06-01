"""Integration tests for GraphDBConnection.fuzzy_find_node.

Hits the live Neo4j configured via ~/.educedb / env vars.

Run:
    uv run python -m unittest tests/integration/test_fuzzy_find_node.py
"""
import unittest

from educelab import hercdb


class TestFuzzyFindNode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()

    # --- label validation & input guards ---

    def test_invalid_label_raises(self):
        with self.assertRaises(ValueError):
            self.db.fuzzy_find_node("anything", label="Bogus")

    def test_empty_query_returns_empty_list(self):
        self.assertEqual(self.db.fuzzy_find_node("", label="PHerc"), [])
        self.assertEqual(self.db.fuzzy_find_node("   ", label="PHerc"), [])

    # --- PHerc lookups ---

    def test_exact_pherc_match_scores_100(self):
        results = self.db.fuzzy_find_node("421", label="PHerc")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["displayName"], "421")
        self.assertEqual(results[0]["score"], 100)
        # Parents are contextual-only for a PHerc — both None.
        self.assertIsNone(results[0]["parent_pherc"])
        self.assertIsNone(results[0]["parent_cornice"])

    def test_whitespace_variant_short_circuits_to_exact(self):
        # "118 a" normalizes to "118a" — should match the real "118a"
        # node at score 100, not get fuzzy-ranked.
        results = self.db.fuzzy_find_node("118 a", label="PHerc")
        self.assertGreaterEqual(len(results), 1)
        names = [r["displayName"] for r in results]
        self.assertIn("118a", names)
        self.assertEqual(results[0]["score"], 100)
        self.assertEqual(results[0]["displayName"], "118a")

    def test_case_insensitive_match(self):
        # Whatever case the user types, normalize lowercases before
        # comparison. Use a name that exists in the DB.
        results = self.db.fuzzy_find_node("118A", label="PHerc")
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["displayName"], "118a")
        self.assertEqual(results[0]["score"], 100)

    def test_no_hits_returns_empty(self):
        # Threshold raised so the noise floor doesn't accidentally pick
        # up a stray short-name match.
        results = self.db.fuzzy_find_node(
            "ZZZZZZZZZZZZ", label="PHerc", threshold=80,
        )
        self.assertEqual(results, [])

    def test_threshold_filters_weak_candidates(self):
        # At threshold 99 only the exact match should survive.
        results = self.db.fuzzy_find_node(
            "118 a", label="PHerc", threshold=99,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["score"], 100)

    def test_limit_caps_output(self):
        # Low threshold + small limit — should cap regardless of how
        # many candidates qualify.
        results = self.db.fuzzy_find_node(
            "1", label="PHerc", threshold=0, limit=3,
        )
        self.assertLessEqual(len(results), 3)

    def test_results_sorted_by_score_desc(self):
        results = self.db.fuzzy_find_node(
            "1", label="PHerc", threshold=0, limit=20,
        )
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    # --- Cornice lookups ---

    def test_cornice_with_fuzzy_parent(self):
        # Cass.7 lives under PHerc 72 in the live DB. Fuzzy-resolve the
        # parent (exact "72" -> score 100) and find Cornici under it.
        results = self.db.fuzzy_find_node(
            "Cass", label="Cornice", parent_pherc="72",
        )
        self.assertGreaterEqual(len(results), 1)
        match = next(r for r in results if r["displayName"] == "Cass.7")
        self.assertIsNotNone(match["parent_pherc"])
        self.assertEqual(match["parent_pherc"]["displayName"], "72")
        self.assertEqual(match["parent_pherc"]["score"], 100)
        self.assertIsNone(match["parent_cornice"])

    def test_cornice_without_parent_pherc_has_contextual_parent(self):
        # No parent supplied — parent_pherc still carries the actual
        # parent's displayName, but score is None (contextual, not matched).
        results = self.db.fuzzy_find_node(
            "Cass.7", label="Cornice", limit=5,
        )
        self.assertGreaterEqual(len(results), 1)
        top = results[0]
        self.assertEqual(top["displayName"], "Cass.7")
        self.assertEqual(top["score"], 100)
        self.assertIsNotNone(top["parent_pherc"])
        self.assertIsNotNone(top["parent_pherc"]["displayName"])
        self.assertIsNone(top["parent_pherc"]["score"])

    def test_cornice_unreachable_parent_returns_empty(self):
        # No PHerc can reasonably fuzzy-match a 12-Z name above
        # threshold 75; the chain should short-circuit to [].
        results = self.db.fuzzy_find_node(
            "Cass", label="Cornice", parent_pherc="ZZZZZZZZZZZZ",
        )
        self.assertEqual(results, [])

    # --- Pezzo lookups ---

    def test_pezzo_returns_list_shape(self):
        # We don't assert specific content (Pezzo names vary widely in
        # the DB); just confirm the shape is right when something
        # reasonable comes back, or [] if nothing.
        results = self.db.fuzzy_find_node(
            "1", label="Pezzo", threshold=0, limit=5,
        )
        self.assertIsInstance(results, list)
        for r in results:
            self.assertIn("displayName", r)
            self.assertIn("score", r)
            self.assertIn("parent_pherc", r)
            self.assertIn("parent_cornice", r)


if __name__ == "__main__":
    unittest.main()
