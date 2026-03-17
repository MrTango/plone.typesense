"""Tests for Typesense REST API service endpoints."""
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.typesense.testing import PLONE_TYPESENSE_FUNCTIONAL_TESTING
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from Products.CMFCore.interfaces import ICatalogAware
from unittest import mock
from zope.component import getUtility

import json
import transaction
import unittest

try:
    import plone.restapi  # noqa: F401
    HAS_RESTAPI = True
except ImportError:
    HAS_RESTAPI = False


@unittest.skipUnless(HAS_RESTAPI, "plone.restapi not installed")
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


@unittest.skipUnless(HAS_RESTAPI, "plone.restapi not installed")
class TestTypesenseExtractDataServiceIntegration(unittest.TestCase):
    """Integration tests for the @typesense-extractdata GET endpoint."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_extractdata_returns_400_without_uid(self):
        """Test that endpoint returns 400 when uid parameter is missing."""
        from plone.typesense.services.typesense import TypesenseExtractData

        service = TypesenseExtractData(self.portal, self.request)
        result = service.reply()

        self.assertIn("error", result)
        self.assertEqual(result["error"]["type"], "BadRequest")

    def test_extractdata_returns_404_for_nonexistent_uid(self):
        """Test that endpoint returns 404 when object is not found."""
        from plone.typesense.services.typesense import TypesenseExtractData

        self.request.set("uid", "nonexistent-uid-12345")
        service = TypesenseExtractData(self.portal, self.request)

        with mock.patch(
            "plone.typesense.queueprocessor.IndexProcessor"
        ) as MockProcessor:
            MockProcessor.return_value.get_data.return_value = {}
            result = service.reply()

        self.assertIn("error", result)
        self.assertEqual(result["error"]["type"], "NotFound")

    def test_extractdata_returns_data_for_valid_uid(self):
        """Test that endpoint returns extracted data for a valid UID."""
        from plone.typesense.services.typesense import TypesenseExtractData

        self.request.set("uid", "test-uid-123")
        service = TypesenseExtractData(self.portal, self.request)

        mock_data = {"Title": "Test Document", "Description": "A test"}

        with mock.patch(
            "plone.typesense.queueprocessor.IndexProcessor"
        ) as MockProcessor:
            MockProcessor.return_value.get_data.return_value = mock_data
            result = service.reply()

        self.assertIn("data", result)
        self.assertEqual(result["uid"], "test-uid-123")
        self.assertEqual(result["data"]["Title"], "Test Document")
        self.assertEqual(result["data"]["id"], "test-uid-123")

    def test_extractdata_handles_processor_error(self):
        """Test that endpoint handles errors from IndexProcessor gracefully."""
        from plone.typesense.services.typesense import TypesenseExtractData

        self.request.set("uid", "error-uid")
        service = TypesenseExtractData(self.portal, self.request)

        with mock.patch(
            "plone.typesense.queueprocessor.IndexProcessor"
        ) as MockProcessor:
            MockProcessor.return_value.get_data.side_effect = Exception(
                "Processing error"
            )
            result = service.reply()

        self.assertIn("error", result)
        self.assertEqual(result["error"]["type"], "InternalServerError")

    def test_extractdata_strips_whitespace_from_uid(self):
        """Test that uid parameter whitespace is stripped."""
        from plone.typesense.services.typesense import TypesenseExtractData

        self.request.set("uid", "  test-uid-123  ")
        service = TypesenseExtractData(self.portal, self.request)

        mock_data = {"Title": "Test"}

        with mock.patch(
            "plone.typesense.queueprocessor.IndexProcessor"
        ) as MockProcessor:
            MockProcessor.return_value.get_data.return_value = mock_data
            result = service.reply()

        MockProcessor.return_value.get_data.assert_called_once_with("test-uid-123")
        self.assertEqual(result["uid"], "test-uid-123")


@unittest.skipUnless(HAS_RESTAPI, "plone.restapi not installed")
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
            with mock.patch(
                "plone.typesense.services.typesense._reindex_all", return_value=10
            ):
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

    def test_convert_uses_index_processor(self):
        """Test that convert uses IndexProcessor.get_data for proper extraction."""
        from plone.typesense.services.typesense import TypesenseConvert

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True

        mock_brain = mock.MagicMock()
        mock_brain.UID = "uid-1"

        mock_catalog = mock.MagicMock()
        mock_catalog.unrestrictedSearchResults.return_value = [mock_brain]

        mock_data = {"Title": "Test", "Description": "Desc"}

        service = TypesenseConvert(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            with mock.patch(
                "plone.typesense.services.typesense.api.portal.get_tool",
                return_value=mock_catalog,
            ):
                with mock.patch(
                    "plone.typesense.queueprocessor.IndexProcessor"
                ) as MockProcessor:
                    MockProcessor.return_value.get_data.return_value = mock_data
                    result = service.reply()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["indexed_count"], 1)
        MockProcessor.return_value.get_data.assert_called_once_with("uid-1")
        # Verify that the connector received dicts, not raw objects
        call_args = mock_connector.index.call_args[0][0]
        self.assertIsInstance(call_args[0], dict)
        self.assertEqual(call_args[0]["id"], "uid-1")


@unittest.skipUnless(HAS_RESTAPI, "plone.restapi not installed")
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
            with mock.patch(
                "plone.typesense.services.typesense._reindex_all", return_value=5
            ):
                result = service.reply()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["indexed_count"], 5)

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
            with mock.patch(
                "plone.typesense.services.typesense._reindex_all",
                side_effect=Exception("Reindex error"),
            ):
                result = service.reply()

        self.assertIn("error", result)

    def test_rebuild_uses_index_processor(self):
        """Test that rebuild uses IndexProcessor.get_data for proper extraction."""
        from plone.typesense.services.typesense import TypesenseRebuild

        mock_connector = mock.MagicMock()
        mock_connector.enabled = True

        mock_brain = mock.MagicMock()
        mock_brain.UID = "uid-1"

        mock_catalog = mock.MagicMock()
        mock_catalog.unrestrictedSearchResults.return_value = [mock_brain]

        mock_data = {"Title": "Test"}

        service = TypesenseRebuild(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            with mock.patch(
                "plone.typesense.services.typesense.api.portal.get_tool",
                return_value=mock_catalog,
            ):
                with mock.patch(
                    "plone.typesense.queueprocessor.IndexProcessor"
                ) as MockProcessor:
                    MockProcessor.return_value.get_data.return_value = mock_data
                    result = service.reply()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["indexed_count"], 1)
        # Verify dicts are passed, not raw objects
        call_args = mock_connector.index.call_args[0][0]
        self.assertIsInstance(call_args[0], dict)


@unittest.skipUnless(HAS_RESTAPI, "plone.restapi not installed")
class TestReindexAllHelper(unittest.TestCase):
    """Tests for the shared _reindex_all helper function."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_reindex_all_skips_brains_without_uid(self):
        """Brains with no UID should be skipped."""
        from plone.typesense.services.typesense import _reindex_all

        mock_connector = mock.MagicMock()
        mock_brain_no_uid = mock.MagicMock()
        mock_brain_no_uid.UID = None
        mock_brain_valid = mock.MagicMock()
        mock_brain_valid.UID = "uid-1"

        mock_catalog = mock.MagicMock()
        mock_catalog.unrestrictedSearchResults.return_value = [
            mock_brain_no_uid,
            mock_brain_valid,
        ]

        mock_data = {"Title": "Test"}

        with mock.patch(
            "plone.typesense.services.typesense.api.portal.get_tool",
            return_value=mock_catalog,
        ):
            with mock.patch(
                "plone.typesense.queueprocessor.IndexProcessor"
            ) as MockProcessor:
                MockProcessor.return_value.get_data.return_value = mock_data
                count = _reindex_all(mock_connector)

        self.assertEqual(count, 1)
        MockProcessor.return_value.get_data.assert_called_once_with("uid-1")

    def test_reindex_all_handles_per_object_errors(self):
        """Errors extracting individual objects should not abort the reindex."""
        from plone.typesense.services.typesense import _reindex_all

        mock_connector = mock.MagicMock()

        mock_brain_1 = mock.MagicMock()
        mock_brain_1.UID = "uid-1"
        mock_brain_2 = mock.MagicMock()
        mock_brain_2.UID = "uid-2"

        mock_catalog = mock.MagicMock()
        mock_catalog.unrestrictedSearchResults.return_value = [
            mock_brain_1,
            mock_brain_2,
        ]

        with mock.patch(
            "plone.typesense.services.typesense.api.portal.get_tool",
            return_value=mock_catalog,
        ):
            with mock.patch(
                "plone.typesense.queueprocessor.IndexProcessor"
            ) as MockProcessor:
                MockProcessor.return_value.get_data.side_effect = [
                    Exception("bad object"),
                    {"Title": "Good"},
                ]
                count = _reindex_all(mock_connector)

        self.assertEqual(count, 1)

    def test_reindex_all_handles_batch_errors(self):
        """Errors in one batch should not abort subsequent batches."""
        from plone.typesense.services.typesense import _reindex_all

        mock_connector = mock.MagicMock()
        # First call raises, second succeeds
        mock_connector.index.side_effect = [Exception("batch error"), None]

        # Create enough brains to fill 2 batches (bulk_size defaults to 50)
        brains = []
        for i in range(60):
            brain = mock.MagicMock()
            brain.UID = f"uid-{i}"
            brains.append(brain)

        mock_catalog = mock.MagicMock()
        mock_catalog.unrestrictedSearchResults.return_value = brains

        with mock.patch(
            "plone.typesense.services.typesense.api.portal.get_tool",
            return_value=mock_catalog,
        ):
            with mock.patch(
                "plone.typesense.queueprocessor.IndexProcessor"
            ) as MockProcessor:
                MockProcessor.return_value.get_data.return_value = {"Title": "Test"}
                count = _reindex_all(mock_connector)

        # First batch of 50 fails (count=0), second batch of 10 succeeds (count=10)
        self.assertEqual(count, 10)
        self.assertEqual(mock_connector.index.call_count, 2)


@unittest.skipUnless(HAS_RESTAPI, "plone.restapi not installed")
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

        mock_catalog.unrestrictedSearchResults.return_value = [
            mock_brain_1,
            mock_brain_2,
        ]

        mock_data = {"Title": "Missing doc"}

        service = TypesenseSync(self.portal, self.request)
        with mock.patch(
            "plone.typesense.services.typesense.getUtility",
            return_value=mock_connector,
        ):
            with mock.patch(
                "plone.typesense.services.typesense.api.portal.get_tool",
                return_value=mock_catalog,
            ):
                with mock.patch(
                    "plone.typesense.queueprocessor.IndexProcessor"
                ) as MockProcessor:
                    MockProcessor.return_value.get_data.return_value = mock_data
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
