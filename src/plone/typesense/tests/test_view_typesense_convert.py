# -*- coding: utf-8 -*-
from unittest import mock

from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING
from plone.typesense.views.typesense_convert import ITypesenseConvert
from plone.typesense.views.typesense_convert import TypesenseConvert
from zope.component import getMultiAdapter

import unittest


class TestTypesenseConvertViewRegistration(unittest.TestCase):
    """Test the convert view is properly registered."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_convert_view_is_registered(self):
        view = getMultiAdapter(
            (self.portal, self.portal.REQUEST),
            name="typesense-convert",
        )
        self.assertTrue(ITypesenseConvert.providedBy(view))

    def test_convert_view_instance(self):
        view = getMultiAdapter(
            (self.portal, self.portal.REQUEST),
            name="typesense-convert",
        )
        self.assertIsInstance(view, TypesenseConvert)


class TestTypesenseConvertViewLogic(unittest.TestCase):
    """Test the convert view logic with mocked Typesense."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.doc1 = api.content.create(
            self.portal, "Document", "doc1", title="Document 1"
        )
        self.doc2 = api.content.create(
            self.portal, "Document", "doc2", title="Document 2"
        )

    def _make_view(self):
        view = getMultiAdapter(
            (self.portal, self.portal.REQUEST),
            name="typesense-convert",
        )
        return view

    @mock.patch(
        "plone.typesense.views.typesense_convert.getUtility"
    )
    @mock.patch(
        "plone.typesense.queueprocessor.IndexProcessor"
    )
    def test_convert_clears_and_reindexes(self, mock_processor_cls, mock_get_utility):
        """Test that convert clears collection and reindexes all content."""
        view = self._make_view()

        mock_connector = mock.MagicMock()
        mock_connector.collection_base_name = "test_collection"
        mock_get_utility.return_value = mock_connector

        mock_processor = mock.MagicMock()
        mock_processor.get_data.return_value = {"Title": "Test", "id": "test"}
        mock_processor_cls.return_value = mock_processor

        results = view._convert()

        # Verify clear was called
        mock_connector.clear.assert_called_once()

        # Verify index was called with documents
        self.assertTrue(mock_connector.index.called)
        self.assertEqual(results["collection_name"], "test_collection")
        self.assertGreater(results["indexed"], 0)

    @mock.patch(
        "plone.typesense.views.typesense_convert.getUtility"
    )
    @mock.patch(
        "plone.typesense.queueprocessor.IndexProcessor"
    )
    def test_reindex_all_handles_errors_gracefully(
        self, mock_processor_cls, mock_get_utility
    ):
        """Test that reindex handles individual object errors gracefully."""
        view = self._make_view()

        mock_connector = mock.MagicMock()
        mock_connector.collection_base_name = "test_collection"
        mock_get_utility.return_value = mock_connector

        mock_processor = mock.MagicMock()
        # First call succeeds, second raises
        mock_processor.get_data.side_effect = [
            {"Title": "Test 1"},
            Exception("Object error"),
            {"Title": "Test 2"},
        ]
        mock_processor_cls.return_value = mock_processor

        # Should not raise, should skip erroring objects
        indexed = view._reindex_all(mock_connector)
        # Some objects should have been indexed despite errors
        self.assertIsInstance(indexed, int)

    @mock.patch(
        "plone.typesense.views.typesense_convert.getUtility"
    )
    @mock.patch(
        "plone.typesense.queueprocessor.IndexProcessor"
    )
    def test_convert_result_structure(self, mock_processor_cls, mock_get_utility):
        """Test that convert returns proper result structure."""
        view = self._make_view()

        mock_connector = mock.MagicMock()
        mock_connector.collection_base_name = "my_collection"
        mock_get_utility.return_value = mock_connector

        mock_processor = mock.MagicMock()
        mock_processor.get_data.return_value = {"Title": "Test"}
        mock_processor_cls.return_value = mock_processor

        results = view._convert()

        self.assertIn("collection_name", results)
        self.assertIn("indexed", results)
        self.assertEqual(results["collection_name"], "my_collection")
        self.assertIsInstance(results["indexed"], int)
