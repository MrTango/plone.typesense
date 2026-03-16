"""Tests for BrainFactory and TypesenseBrain — Typesense result format."""
import ast
import os
import unittest
from unittest.mock import MagicMock

from plone.typesense.result import BrainFactory, TypesenseBrain


RESULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "result.py"
)


class TestTypesenseBrain(unittest.TestCase):
    """Test TypesenseBrain with Typesense document format."""

    def test_getPath_flat_string(self):
        brain = TypesenseBrain({"path": "/plone/doc1"}, MagicMock())
        self.assertEqual(brain.getPath(), "/plone/doc1")

    def test_getPath_nested_dict_fallback(self):
        brain = TypesenseBrain({"path": {"path": "/plone/doc1"}}, MagicMock())
        self.assertEqual(brain.getPath(), "/plone/doc1")

    def test_getattr_returns_record_value(self):
        brain = TypesenseBrain({"Title": "My Doc", "path": "/p"}, MagicMock())
        self.assertEqual(brain.Title, "My Doc")

    def test_getattr_raises_for_missing(self):
        brain = TypesenseBrain({"path": "/p"}, MagicMock())
        with self.assertRaises(AttributeError):
            _ = brain.nonexistent

    def test_has_key(self):
        brain = TypesenseBrain({"path": "/p", "Title": "T"}, MagicMock())
        self.assertTrue(brain.has_key("Title"))
        self.assertFalse(brain.has_key("Missing"))

    def test_contains(self):
        brain = TypesenseBrain({"path": "/p"}, MagicMock())
        self.assertIn("path", brain)
        self.assertNotIn("missing", brain)

    def test_getRID_returns_minus_one(self):
        brain = TypesenseBrain({"path": "/p"}, MagicMock())
        self.assertEqual(brain.getRID(), -1)


class TestBrainFactorySource(unittest.TestCase):
    """Verify BrainFactory uses Typesense format, not ES format."""

    def setUp(self):
        with open(RESULT_PATH) as f:
            self.source = f.read()

    def test_reads_document_key_not_fields(self):
        """BrainFactory must read from result['document'], not result['fields']."""
        # Find BrainFactory function
        self.assertIn('result.get("document"', self.source)
        self.assertNotIn('result.get("fields"', self.source)

    def test_reads_highlights_not_highlight(self):
        """BrainFactory must use 'highlights' (Typesense), not 'highlight' (ES)."""
        self.assertIn('result.get("highlights")', self.source)

    def test_uses_snippets_key(self):
        """Typesense highlights use 'snippets', not direct lists."""
        self.assertIn('"snippets"', self.source)


class TestBrainFactory(unittest.TestCase):
    """Test BrainFactory processes Typesense result format."""

    def _make_manager(self, highlight=False, highlight_threshold=500):
        mgr = MagicMock()
        mgr.highlight = highlight
        mgr.highlight_threshold = highlight_threshold
        mgr.catalog._catalog = MagicMock()
        return mgr

    def _make_result(self, path="/plone/doc1", highlights=None):
        result = {"document": {"path": path, "Title": "Doc"}}
        if highlights:
            result["highlights"] = highlights
        return result

    def test_extracts_path_from_document(self):
        """BrainFactory reads path from result['document']['path']."""
        mgr = self._make_manager()
        factory = BrainFactory(mgr)
        result = self._make_result()

        with unittest.mock.patch("plone.typesense.result.get_brain_from_path") as mock_get:
            mock_brain = MagicMock()
            mock_get.return_value = mock_brain
            brain = factory(result)
            mock_get.assert_called_once_with(mgr.catalog._catalog, "/plone/doc1")
            self.assertEqual(brain, mock_brain)

    def test_falls_back_to_typesense_brain(self):
        """When ZCatalog brain not found, creates TypesenseBrain."""
        mgr = self._make_manager()
        mgr.get_record_by_path.return_value = {"path": "/plone/doc1", "Title": "Doc"}
        factory = BrainFactory(mgr)

        with unittest.mock.patch("plone.typesense.result.get_brain_from_path", return_value=None):
            brain = factory(self._make_result())
            self.assertIsInstance(brain, TypesenseBrain)

    def test_returns_none_when_no_path(self):
        mgr = self._make_manager()
        factory = BrainFactory(mgr)
        result = {"document": {}}
        brain = factory(result)
        self.assertIsNone(brain)

    def test_highlight_with_typesense_format(self):
        mgr = self._make_manager(highlight=True, highlight_threshold=500)
        factory = BrainFactory(mgr)

        highlights = [
            {"field": "SearchableText", "snippets": ["<mark>test</mark>", "another <mark>frag</mark>"]},
            {"field": "Title", "snippets": ["<mark>Test</mark> Title"]},
        ]

        with unittest.mock.patch("plone.typesense.result.get_brain_from_path") as mock_get:
            mock_brain = MagicMock()
            mock_get.return_value = mock_brain
            factory(self._make_result(highlights=highlights))
            mock_brain.__setitem__.assert_called_once_with(
                "Description",
                "<mark>test</mark> ... another <mark>frag</mark>",
            )

    def test_highlight_threshold_limits_fragments(self):
        mgr = self._make_manager(highlight=True, highlight_threshold=20)
        factory = BrainFactory(mgr)

        highlights = [
            {"field": "SearchableText", "snippets": [
                "Short text here",  # 15 chars
                "This exceeds threshold",  # total > 20
            ]},
        ]

        with unittest.mock.patch("plone.typesense.result.get_brain_from_path") as mock_get:
            mock_brain = MagicMock()
            mock_get.return_value = mock_brain
            factory(self._make_result(highlights=highlights))
            mock_brain.__setitem__.assert_called_once_with(
                "Description", "Short text here"
            )

    def test_no_highlight_when_disabled(self):
        mgr = self._make_manager(highlight=False)
        factory = BrainFactory(mgr)

        with unittest.mock.patch("plone.typesense.result.get_brain_from_path") as mock_get:
            mock_brain = MagicMock()
            mock_get.return_value = mock_brain
            factory(self._make_result(highlights=[
                {"field": "SearchableText", "snippets": ["test"]}
            ]))
            mock_brain.__setitem__.assert_not_called()


if __name__ == "__main__":
    unittest.main()
