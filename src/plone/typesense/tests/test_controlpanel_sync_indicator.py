# -*- coding: utf-8 -*-
import unittest
from unittest import mock

try:
    from plone import api
    from plone.app.testing import setRoles
    from plone.app.testing import TEST_USER_ID
    from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
        TypesenseControlpanelFormWrapper,
    )
    from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING

    HAS_RESTAPI = True
except ImportError:
    HAS_RESTAPI = False


if HAS_RESTAPI:

    class TestSyncIndicator(unittest.TestCase):
        """Test the data sync indicator in the control panel."""

        layer = PLONE_TYPESENSE_INTEGRATION_TESTING

        def setUp(self):
            self.portal = self.layer["portal"]
            setRoles(self.portal, TEST_USER_ID, ["Manager"])

        def _make_wrapper(self):
            wrapper = TypesenseControlpanelFormWrapper.__new__(
                TypesenseControlpanelFormWrapper
            )
            wrapper.context = self.portal
            wrapper.request = self.portal.REQUEST
            return wrapper

        @mock.patch(
            "plone.typesense.controlpanels.typesense_controlpanel.controlpanel.getUtility"
        )
        def test_data_sync_status_in_sync(self, mock_get_utility):
            """Test sync indicator when counts match."""
            wrapper = self._make_wrapper()

            mock_client = mock.MagicMock()
            mock_client.collections.__getitem__().retrieve.return_value = {
                "num_documents": 5,
            }
            mock_connector = mock.MagicMock()
            mock_connector.enabled = True
            mock_connector.get_client.return_value = mock_client
            mock_connector.collection_base_name = "test_collection"
            mock_get_utility.return_value = mock_connector

            # Mock catalog to return 5 results
            with mock.patch.object(
                api.portal, "get_tool"
            ) as mock_get_tool:
                mock_catalog = mock.MagicMock()
                mock_catalog.unrestrictedSearchResults.return_value = [1, 2, 3, 4, 5]
                mock_get_tool.return_value = mock_catalog

                status = wrapper.data_sync_status

            self.assertIsNotNone(status)
            self.assertEqual(status["catalog_count"], 5)
            self.assertEqual(status["typesense_count"], 5)
            self.assertTrue(status["in_sync"])
            self.assertEqual(status["difference"], 0)

        @mock.patch(
            "plone.typesense.controlpanels.typesense_controlpanel.controlpanel.getUtility"
        )
        def test_data_sync_status_out_of_sync(self, mock_get_utility):
            """Test sync indicator when counts differ."""
            wrapper = self._make_wrapper()

            mock_client = mock.MagicMock()
            mock_client.collections.__getitem__().retrieve.return_value = {
                "num_documents": 3,
            }
            mock_connector = mock.MagicMock()
            mock_connector.enabled = True
            mock_connector.get_client.return_value = mock_client
            mock_connector.collection_base_name = "test_collection"
            mock_get_utility.return_value = mock_connector

            with mock.patch.object(
                api.portal, "get_tool"
            ) as mock_get_tool:
                mock_catalog = mock.MagicMock()
                mock_catalog.unrestrictedSearchResults.return_value = [1, 2, 3, 4, 5]
                mock_get_tool.return_value = mock_catalog

                status = wrapper.data_sync_status

            self.assertIsNotNone(status)
            self.assertEqual(status["catalog_count"], 5)
            self.assertEqual(status["typesense_count"], 3)
            self.assertFalse(status["in_sync"])
            self.assertEqual(status["difference"], 2)

        @mock.patch(
            "plone.typesense.controlpanels.typesense_controlpanel.controlpanel.getUtility"
        )
        def test_data_sync_status_disabled(self, mock_get_utility):
            """Test sync indicator returns None when Typesense is disabled."""
            wrapper = self._make_wrapper()

            mock_connector = mock.MagicMock()
            mock_connector.enabled = False
            mock_get_utility.return_value = mock_connector

            status = wrapper.data_sync_status
            self.assertIsNone(status)

        @mock.patch(
            "plone.typesense.controlpanels.typesense_controlpanel.controlpanel.getUtility"
        )
        def test_data_sync_status_connection_error(self, mock_get_utility):
            """Test sync indicator returns None on connection error."""
            wrapper = self._make_wrapper()

            mock_connector = mock.MagicMock()
            mock_connector.enabled = True
            mock_connector.get_client.side_effect = Exception("Connection refused")
            mock_get_utility.return_value = mock_connector

            status = wrapper.data_sync_status
            self.assertIsNone(status)

        @mock.patch(
            "plone.typesense.controlpanels.typesense_controlpanel.controlpanel.getUtility"
        )
        def test_connection_status_healthy(self, mock_get_utility):
            """Test connection status when Typesense is healthy."""
            wrapper = self._make_wrapper()

            mock_client = mock.MagicMock()
            mock_client.operations.is_healthy.return_value = True
            mock_connector = mock.MagicMock()
            mock_connector.enabled = True
            mock_connector.get_client.return_value = mock_client
            mock_get_utility.return_value = mock_connector

            self.assertTrue(wrapper.connection_status)

        @mock.patch(
            "plone.typesense.controlpanels.typesense_controlpanel.controlpanel.getUtility"
        )
        def test_connection_status_unhealthy(self, mock_get_utility):
            """Test connection status when Typesense connection fails."""
            wrapper = self._make_wrapper()

            mock_connector = mock.MagicMock()
            mock_connector.enabled = True
            mock_connector.get_client.side_effect = Exception("Connection error")
            mock_get_utility.return_value = mock_connector

            self.assertFalse(wrapper.connection_status)

        @mock.patch(
            "plone.typesense.controlpanels.typesense_controlpanel.controlpanel.getUtility"
        )
        def test_connection_status_disabled(self, mock_get_utility):
            """Test connection status returns None when disabled."""
            wrapper = self._make_wrapper()

            mock_connector = mock.MagicMock()
            mock_connector.enabled = False
            mock_get_utility.return_value = mock_connector

            self.assertIsNone(wrapper.connection_status)
