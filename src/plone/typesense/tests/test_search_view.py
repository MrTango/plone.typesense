"""Tests for the TypesenseSearchView."""

import unittest
from unittest.mock import MagicMock, patch

from plone.typesense.browser.search import TypesenseSearchView


class TestTypesenseSearchView(unittest.TestCase):
    """Unit tests for the custom search view."""

    def _make_view(self, form=None):
        """Create a view instance with a mock request."""
        request = MagicMock()
        request.form = form or {}
        context = MagicMock()
        view = TypesenseSearchView(context, request)
        return view

    def test_build_query_simple(self):
        view = self._make_view({"SearchableText": "plone cms"})
        query = view._build_query()
        self.assertEqual(query["SearchableText"], "plone cms")

    def test_build_query_preserves_raw_text(self):
        """Ensure the search text is not mangled (no wildcards added)."""
        view = self._make_view({"SearchableText": "exact phrase search"})
        query = view._build_query()
        self.assertEqual(query["SearchableText"], "exact phrase search")
        self.assertNotIn("*", query["SearchableText"])

    def test_build_query_multiple_params(self):
        view = self._make_view({
            "SearchableText": "plone",
            "portal_type": "Document",
            "review_state": "published",
        })
        query = view._build_query()
        self.assertEqual(query["SearchableText"], "plone")
        self.assertEqual(query["portal_type"], "Document")
        self.assertEqual(query["review_state"], "published")

    def test_build_query_skips_empty_values(self):
        view = self._make_view({
            "SearchableText": "plone",
            "portal_type": "",
        })
        query = view._build_query()
        self.assertIn("SearchableText", query)
        self.assertNotIn("portal_type", query)

    def test_build_query_skips_internal_params(self):
        view = self._make_view({
            "SearchableText": "plone",
            "_authenticator": "abc123",
            "form.submitted": "1",
        })
        query = view._build_query()
        self.assertIn("SearchableText", query)
        self.assertNotIn("_authenticator", query)
        self.assertNotIn("form.submitted", query)

    def test_build_query_empty_form(self):
        view = self._make_view({})
        query = view._build_query()
        self.assertEqual(query, {})

    def test_search_term_property(self):
        view = self._make_view({"SearchableText": "my search"})
        self.assertEqual(view.search_term, "my search")

    def test_search_term_property_missing(self):
        view = self._make_view({})
        self.assertEqual(view.search_term, "")

    def test_batch_size_default(self):
        view = self._make_view({})
        self.assertEqual(view.batch_size, 20)

    def test_batch_size_from_request(self):
        view = self._make_view({"b_size": "50"})
        self.assertEqual(view.batch_size, 50)

    def test_batch_size_invalid(self):
        view = self._make_view({"b_size": "abc"})
        self.assertEqual(view.batch_size, 20)

    def test_batch_start_default(self):
        view = self._make_view({})
        self.assertEqual(view.batch_start, 0)

    def test_batch_start_from_request(self):
        view = self._make_view({"b_start": "40"})
        self.assertEqual(view.batch_start, 40)

    def test_results_empty_query_returns_empty(self):
        view = self._make_view({})
        results = view.results()
        self.assertEqual(results, [])

    def test_results_fallback_when_no_manager(self):
        """When no ITypesenseManager utility exists, fall back to catalog."""
        view = self._make_view({"SearchableText": "test"})
        mock_catalog = MagicMock()
        mock_catalog.searchResults.return_value = ["brain1"]
        with patch("plone.typesense.browser.search.queryUtility", return_value=None):
            with patch("plone.typesense.browser.search.api.portal.get_tool", return_value=mock_catalog):
                results = view.results()
        mock_catalog.searchResults.assert_called_once()
        self.assertEqual(results, ["brain1"])


if __name__ == "__main__":
    unittest.main()
