# -*- coding: utf-8 -*-
"""Tests for Typesense REST API service endpoints."""
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.typesense.testing import PLONE_TYPESENSE_FUNCTIONAL_TESTING
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from unittest import mock
from zope.component import getUtility

import json
import transaction
import unittest


class TestTypesenseInfoServiceIntegration(unittest.TestCase):
    """Integration tests for the @typesense-info GET endpoint."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_info_endpoint_returns_disabled_when_not_enabled(self):
        """Test that info endpoint reports disabled status."""
        from plone.typesense.services.typesense import TypesenseInfo

        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.enabled", False
        )

        service = TypesenseInfo(self.portal, self.request)
        result = service.reply()

        self.assertIn("@id", result)
        self.assertFalse(result["enabled"])
        self.assertEqual(result["connection"]["status"], "disabled")

    def test_info_endpoint_returns_connection_error_on_bad_config(self):
        """Test that info endpoint handles connection errors gracefully."""
        from plone.typesense.services.typesense import TypesenseInfo

        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.enabled", True
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", "bad-key"
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.host", "nonexistent-host"
        )

        service = TypesenseInfo(self.portal, self.request)

        # Mock the connector to simulate connection failure
        with mock.patch.object(
            ITypesenseConnector,
            "providedBy",
            return_value=True,
        ):
            mock_connector = mock.MagicMock()
            mock_connector.enabled = True
            mock_connector.get_host = "nonexistent-host"
            mock_connector.get_port = "8108"
            mock_connector.get_protocol = "http"
            mock_client = mock.MagicMock()
            mock_client.operations.is_healthy.side_effect = Exception(
                "Connection refused"
            )
            mock_connector.get_client.return_value = mock_client

            with mock.patch(
                "plone.typesense.services.typesense.getUtility",
                return_value=mock_connector,
            ):
                result = service.reply()

        self.assertEqual(result["connection"]["status"], "error")
        self.assertIn("message", result["connection"])

    def test_info_endpoint_returns_collection_info(self):
        """Test that info endpoint returns collection details when connected."""
        from plone.typesense.services.typesense import TypesenseInfo

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True
        mock_connector.get_host = "localhost"
        mock_connector.get_port = "8108"
        mock_connector.get_protocol = "http"
        mock_connector.collection_base_name = "test-collection"

        mock_client = mock.MagicMock()
        mock_client.operations.is_healthy.return_value = True
        mock_client.collections.__getitem__.return_value.retrieve.return_value = {
            "name": "test-collection",
            "num_documents": 42,
            "fields": [{"name": "Title", "type": "string"}],
            "default_sorting_field": "sortable_title",
        }
        mock_connector.get_client.return_value = mock_client
        mock_connector._get_current_aliased_collection_name.return_value = (
            "test-collection-1"
        )

        service = TypesenseInfo(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            result = service.reply()

        self.assertTrue(result["enabled"])
        self.assertEqual(result["connection"]["status"], "ok")
        self.assertEqual(result["collection"]["name"], "test-collection")
        self.assertEqual(result["collection"]["num_documents"], 42)
        self.assertEqual(result["collection"]["aliased_name"], "test-collection-1")
        self.assertIn("fields", result["collection"])


class TestTypesenseConvertServiceIntegration(unittest.TestCase):
    """Integration tests for the @typesense-convert POST endpoint."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_convert_returns_error_when_disabled(self):
        """Test that convert endpoint rejects requests when disabled."""
        from plone.typesense.services.typesense import TypesenseConvert

        mock_connector = mock.MagicMock()
        mock_connector.enabled = False

        service = TypesenseConvert(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            result = service.reply()

        self.assertIn("error", result)
        self.assertEqual(result["error"]["type"], "BadRequest")

    def test_convert_clears_and_reindexes(self):
        """Test that convert endpoint clears collection and reindexes."""
        from plone.typesense.services.typesense import TypesenseConvert

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True

        service = TypesenseConvert(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            with mock.patch.object(service, "_reindex_all", return_value=10):
                result = service.reply()

        mock_connector.clear.assert_called_once()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["indexed_count"], 10)

    def test_convert_handles_errors(self):
        """Test that convert endpoint handles errors gracefully."""
        from plone.typesense.services.typesense import TypesenseConvert

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True
        mock_connector.clear.side_effect = Exception("Typesense unavailable")

        service = TypesenseConvert(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            result = service.reply()

        self.assertIn("error", result)
        self.assertEqual(result["error"]["type"], "InternalServerError")


class TestTypesenseRebuildServiceIntegration(unittest.TestCase):
    """Integration tests for the @typesense-rebuild POST endpoint."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_rebuild_returns_error_when_disabled(self):
        """Test that rebuild endpoint rejects requests when disabled."""
        from plone.typesense.services.typesense import TypesenseRebuild

        mock_connector = mock.MagicMock()
        mock_connector.enabled = False

        service = TypesenseRebuild(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            result = service.reply()

        self.assertIn("error", result)

    def test_rebuild_indexes_content(self):
        """Test that rebuild endpoint indexes all content."""
        from plone.typesense.services.typesense import TypesenseRebuild

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True

        service = TypesenseRebuild(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            # Mock ZopeFindAndApply to not actually traverse
            with mock.patch.object(
                self.portal, "ZopeFindAndApply"
            ) as mock_find:
                result = service.reply()

        self.assertEqual(result["status"], "ok")
        self.assertIn("indexed_count", result)

    def test_rebuild_handles_errors(self):
        """Test that rebuild endpoint handles errors gracefully."""
        from plone.typesense.services.typesense import TypesenseRebuild

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True

        service = TypesenseRebuild(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            with mock.patch.object(
                self.portal,
                "ZopeFindAndApply",
                side_effect=Exception("Traversal error"),
            ):
                result = service.reply()

        self.assertIn("error", result)


class TestTypesenseSyncServiceIntegration(unittest.TestCase):
    """Integration tests for the @typesense-sync POST endpoint."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_sync_returns_error_when_disabled(self):
        """Test that sync endpoint rejects requests when disabled."""
        from plone.typesense.services.typesense import TypesenseSync

        mock_connector = mock.MagicMock()
        mock_connector.enabled = False

        service = TypesenseSync(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            result = service.reply()

        self.assertIn("error", result)

    def test_sync_detects_missing_and_orphaned(self):
        """Test that sync endpoint identifies missing and orphaned documents."""
        from plone.typesense.services.typesense import TypesenseSync

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True
        mock_connector.collection_base_name = "test-collection"

        # Mock Typesense client with some document IDs
        mock_client = mock.MagicMock()
        mock_client.collections.__getitem__.return_value.documents.search.return_value = {
            "hits": [
                {"document": {"id": "uid-1"}},
                {"document": {"id": "uid-orphan"}},
            ]
        }
        mock_connector.get_client.return_value = mock_client

        # Mock catalog with different UIDs
        mock_catalog = mock.MagicMock()
        mock_brain_1 = mock.MagicMock()
        mock_brain_1.UID = "uid-1"
        mock_brain_2 = mock.MagicMock()
        mock_brain_2.UID = "uid-missing"
        mock_brain_2_obj = mock.MagicMock()
        ICatalogAware.providedBy = mock.MagicMock(return_value=True)
        mock_brain_2.getObject.return_value = mock_brain_2_obj

        mock_catalog.unrestrictedSearchResults.side_effect = [
            # First call: get all UIDs
            [mock_brain_1, mock_brain_2],
            # Second call: look up missing UID
            [mock_brain_2],
        ]

        service = TypesenseSync(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            with mock.patch(
                "plone.typesense.services.typesense.api.portal.get_tool",
                return_value=mock_catalog,
            ):
                result = service.reply()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["catalog_count"], 2)
        self.assertEqual(result["typesense_count"], 2)
        # uid-missing should be indexed
        self.assertEqual(result["indexed_count"], 1)
        # uid-orphan should be deleted
        self.assertEqual(result["deleted_count"], 1)
        mock_connector.delete.assert_called_once()

    def test_sync_handles_empty_collection(self):
        """Test sync when Typesense collection is empty or missing."""
        from plone.typesense.services.typesense import TypesenseSync

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True
        mock_connector.collection_base_name = "test-collection"

        mock_client = mock.MagicMock()
        mock_client.collections.__getitem__.return_value.documents.search.side_effect = (
            Exception("Collection not found")
        )
        mock_connector.get_client.return_value = mock_client

        mock_catalog = mock.MagicMock()
        mock_catalog.unrestrictedSearchResults.return_value = []

        service = TypesenseSync(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            with mock.patch(
                "plone.typesense.services.typesense.api.portal.get_tool",
                return_value=mock_catalog,
            ):
                result = service.reply()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["typesense_count"], 0)
