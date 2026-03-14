"""Tests for configurable highlighting in TypesenseManager."""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock


class TestHighlightParams(unittest.TestCase):
    """Test the _get_highlight_params method of TypesenseManager."""

    def _make_manager(self, highlight=True, start_tag="<mark>",
                      end_tag="</mark>", fields=None):
        """Create a manager-like object with highlight properties."""
        from plone.typesense.manager import TypesenseManager

        manager = TypesenseManager.__new__(TypesenseManager)

        # Patch the properties that would normally read from the registry
        type(manager).highlight = PropertyMock(return_value=highlight)
        type(manager).highlight_start_tag = PropertyMock(return_value=start_tag)
        type(manager).highlight_end_tag = PropertyMock(return_value=end_tag)
        type(manager).highlight_fields = PropertyMock(
            return_value=fields or ["Title", "Description", "SearchableText"]
        )
        return manager

    def test_highlight_disabled(self):
        manager = self._make_manager(highlight=False)
        params = manager._get_highlight_params()
        self.assertEqual(params, {})

    def test_highlight_enabled_defaults(self):
        manager = self._make_manager(highlight=True)
        params = manager._get_highlight_params()
        self.assertEqual(params["highlight_start_tag"], "<mark>")
        self.assertEqual(params["highlight_end_tag"], "</mark>")
        self.assertEqual(
            params["highlight_fields"],
            "Title,Description,SearchableText"
        )

    def test_highlight_custom_tags(self):
        manager = self._make_manager(
            highlight=True,
            start_tag="<strong>",
            end_tag="</strong>",
        )
        params = manager._get_highlight_params()
        self.assertEqual(params["highlight_start_tag"], "<strong>")
        self.assertEqual(params["highlight_end_tag"], "</strong>")

    def test_highlight_custom_fields(self):
        manager = self._make_manager(
            highlight=True,
            fields=["Title", "body"],
        )
        params = manager._get_highlight_params()
        self.assertEqual(params["highlight_fields"], "Title,body")

    def test_highlight_single_field(self):
        manager = self._make_manager(
            highlight=True,
            fields=["SearchableText"],
        )
        params = manager._get_highlight_params()
        self.assertEqual(params["highlight_fields"], "SearchableText")


class TestControlpanelHighlightFields(unittest.TestCase):
    """Test that highlight fields exist in the control panel schema."""

    def test_highlight_start_tag_in_schema(self):
        from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
            ITypesenseControlpanel,
        )
        self.assertIn("highlight_start_tag", ITypesenseControlpanel.names())

    def test_highlight_end_tag_in_schema(self):
        from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
            ITypesenseControlpanel,
        )
        self.assertIn("highlight_end_tag", ITypesenseControlpanel.names())

    def test_highlight_fields_in_schema(self):
        from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
            ITypesenseControlpanel,
        )
        self.assertIn("highlight_fields", ITypesenseControlpanel.names())

    def test_highlight_start_tag_default(self):
        from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
            ITypesenseControlpanel,
        )
        field = ITypesenseControlpanel["highlight_start_tag"]
        self.assertEqual(field.default, "<mark>")

    def test_highlight_end_tag_default(self):
        from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
            ITypesenseControlpanel,
        )
        field = ITypesenseControlpanel["highlight_end_tag"]
        self.assertEqual(field.default, "</mark>")

    def test_highlight_fields_default(self):
        from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
            ITypesenseControlpanel,
        )
        field = ITypesenseControlpanel["highlight_fields"]
        self.assertEqual(
            field.default,
            ["Title", "Description", "SearchableText"],
        )


if __name__ == "__main__":
    unittest.main()
