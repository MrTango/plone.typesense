"""Tests for faceted search and FacetResult."""

import unittest

from plone.typesense.result import FacetResult


class TestFacetResult(unittest.TestCase):
    """Test the FacetResult class."""

    def _make_raw_facets(self):
        """Return example Typesense facet_counts data."""
        return [
            {
                "field_name": "portal_type",
                "counts": [
                    {"value": "Document", "count": 42},
                    {"value": "News Item", "count": 7},
                    {"value": "File", "count": 3},
                ],
                "stats": {"total_values": 3},
            },
            {
                "field_name": "review_state",
                "counts": [
                    {"value": "published", "count": 38},
                    {"value": "private", "count": 14},
                ],
                "stats": {"total_values": 2},
            },
            {
                "field_name": "Subject",
                "counts": [
                    {"value": "python", "count": 15},
                    {"value": "plone", "count": 12},
                    {"value": "cms", "count": 5},
                ],
                "stats": {"total_values": 3},
            },
        ]

    def test_normalize_facets(self):
        raw = self._make_raw_facets()
        result = FacetResult(results=[], facet_counts=raw, count=52)
        self.assertIn("portal_type", result.facet_counts)
        self.assertIn("review_state", result.facet_counts)
        self.assertIn("Subject", result.facet_counts)

    def test_facet_values_structure(self):
        raw = self._make_raw_facets()
        result = FacetResult(results=[], facet_counts=raw, count=52)
        pt = result.facet_counts["portal_type"]
        self.assertEqual(len(pt), 3)
        self.assertEqual(pt[0]["value"], "Document")
        self.assertEqual(pt[0]["count"], 42)

    def test_get_facet_values(self):
        raw = self._make_raw_facets()
        result = FacetResult(results=[], facet_counts=raw, count=52)
        subjects = result.get_facet_values("Subject")
        self.assertEqual(len(subjects), 3)
        self.assertEqual(subjects[0]["value"], "python")

    def test_get_facet_values_missing_field(self):
        raw = self._make_raw_facets()
        result = FacetResult(results=[], facet_counts=raw, count=52)
        missing = result.get_facet_values("nonexistent")
        self.assertEqual(missing, [])

    def test_empty_facets(self):
        result = FacetResult(results=[], facet_counts=[], count=0)
        self.assertEqual(result.facet_counts, {})

    def test_none_facets(self):
        result = FacetResult(results=[], facet_counts=None, count=0)
        self.assertEqual(result.facet_counts, {})

    def test_count(self):
        raw = self._make_raw_facets()
        result = FacetResult(results=[], facet_counts=raw, count=52)
        self.assertEqual(result.count, 52)
        self.assertEqual(len(result), 52)

    def test_results_attribute(self):
        mock_results = ["brain1", "brain2"]
        result = FacetResult(results=mock_results, facet_counts=[], count=2)
        self.assertEqual(result.results, mock_results)

    def test_raw_facet_counts_preserved(self):
        raw = self._make_raw_facets()
        result = FacetResult(results=[], facet_counts=raw, count=0)
        self.assertEqual(result._raw_facet_counts, raw)


if __name__ == "__main__":
    unittest.main()
