"""Tests for setuphandlers (install/uninstall hooks)."""
import sys
import unittest
from unittest import mock


# Mock heavy Plone dependencies that may not be available in test env
for mod_name in [
    "Products", "Products.CMFPlone", "Products.CMFPlone.interfaces",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock.MagicMock()

from plone.typesense import setuphandlers  # noqa: E402


class TestPostInstall(unittest.TestCase):
    """Test the post_install handler."""

    def test_no_connector_logs_warning(self):
        with mock.patch.object(setuphandlers, "_get_connector", return_value=None):
            with mock.patch.object(setuphandlers, "log") as mock_log:
                setuphandlers.post_install(None)
                mock_log.warning.assert_called_once()
                self.assertIn("not found", mock_log.warning.call_args[0][0])

    def test_not_enabled_skips(self):
        connector = mock.Mock()
        connector.enabled = False
        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log") as mock_log:
                setuphandlers.post_install(None)
                mock_log.info.assert_called_once()
                self.assertIn("not enabled", mock_log.info.call_args[0][0])
        connector.init_collection.assert_not_called()

    def test_connection_failure_logs_warning(self):
        connector = mock.Mock()
        connector.enabled = True
        connector.test_connection.side_effect = Exception("connection refused")
        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log") as mock_log:
                setuphandlers.post_install(None)
                mock_log.warning.assert_called_once()
                self.assertIn("Could not connect", mock_log.warning.call_args[0][0])
        connector.init_collection.assert_not_called()

    def test_successful_install_initializes_collection(self):
        connector = mock.Mock()
        connector.enabled = True
        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log"):
                setuphandlers.post_install(None)
        connector.test_connection.assert_called_once()
        connector.init_collection.assert_called_once()

    def test_init_collection_failure_logs_warning(self):
        connector = mock.Mock()
        connector.enabled = True
        connector.init_collection.side_effect = Exception("schema error")
        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log") as mock_log:
                setuphandlers.post_install(None)
                warning_calls = mock_log.warning.call_args_list
                self.assertTrue(len(warning_calls) >= 1)
                self.assertIn(
                    "Could not initialize",
                    warning_calls[0][0][0],
                )


class TestUninstall(unittest.TestCase):
    """Test the uninstall handler."""

    def test_no_connector_logs_warning(self):
        with mock.patch.object(setuphandlers, "_get_connector", return_value=None):
            with mock.patch.object(setuphandlers, "log") as mock_log:
                setuphandlers.uninstall(None)
                mock_log.warning.assert_called_once()
                self.assertIn("not found", mock_log.warning.call_args[0][0])

    def test_not_enabled_skips(self):
        connector = mock.Mock()
        connector.enabled = False
        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log") as mock_log:
                setuphandlers.uninstall(None)
                mock_log.info.assert_called_once()
                self.assertIn("not enabled", mock_log.info.call_args[0][0])

    def test_connection_failure_logs_warning(self):
        connector = mock.Mock()
        connector.enabled = True
        connector.test_connection.side_effect = Exception("timeout")
        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log") as mock_log:
                setuphandlers.uninstall(None)
                mock_log.warning.assert_called_once()
                self.assertIn("Could not connect", mock_log.warning.call_args[0][0])

    def test_successful_uninstall_deletes_aliased_collection(self):
        """When an alias exists, delete the aliased collection and the alias."""
        connector = mock.Mock()
        connector.enabled = True
        connector.collection_base_name = "plone"

        mock_client = mock.Mock()
        connector.get_client.return_value = mock_client

        # Mock aliases["plone"].retrieve() -> {"collection_name": "plone-1"}
        mock_alias_obj = mock.Mock()
        mock_alias_obj.retrieve.return_value = {"collection_name": "plone-1"}
        mock_client.aliases.__getitem__ = mock.Mock(
            side_effect=lambda key: mock_alias_obj
        )

        # Mock collections["plone-1"].delete()
        mock_collection_obj = mock.Mock()
        mock_client.collections.__getitem__ = mock.Mock(
            return_value=mock_collection_obj
        )

        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log"):
                setuphandlers.uninstall(None)

        connector.test_connection.assert_called_once()
        mock_collection_obj.delete.assert_called_once()
        mock_alias_obj.delete.assert_called_once()

    def test_uninstall_no_alias_deletes_collection_directly(self):
        """When no alias exists, fall back to deleting the collection directly."""
        connector = mock.Mock()
        connector.enabled = True
        connector.collection_base_name = "plone"

        mock_client = mock.Mock()
        connector.get_client.return_value = mock_client

        # Mock aliases["plone"].retrieve() raises (no alias)
        mock_alias_obj = mock.Mock()
        mock_alias_obj.retrieve.side_effect = Exception("not found")
        mock_client.aliases.__getitem__ = mock.Mock(
            return_value=mock_alias_obj
        )

        # Mock collections["plone"].delete()
        mock_collection_obj = mock.Mock()
        mock_client.collections.__getitem__ = mock.Mock(
            return_value=mock_collection_obj
        )

        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log"):
                setuphandlers.uninstall(None)

        mock_client.collections.__getitem__.assert_called_with("plone")
        mock_collection_obj.delete.assert_called_once()

    def test_uninstall_empty_collection_name_skips_deletion(self):
        """When collection_base_name is empty, skip deletion."""
        connector = mock.Mock()
        connector.enabled = True
        connector.collection_base_name = ""
        mock_client = mock.Mock()
        connector.get_client.return_value = mock_client

        with mock.patch.object(setuphandlers, "_get_connector", return_value=connector):
            with mock.patch.object(setuphandlers, "log"):
                setuphandlers.uninstall(None)

        connector.get_client.assert_called_once()


class TestHiddenProfiles(unittest.TestCase):
    """Test the HiddenProfiles utility."""

    def test_hidden_profiles(self):
        hp = setuphandlers.HiddenProfiles()
        profiles = hp.getNonInstallableProfiles()
        self.assertIn("plone.typesense:uninstall", profiles)

    def test_hidden_products(self):
        hp = setuphandlers.HiddenProfiles()
        products = hp.getNonInstallableProducts()
        self.assertIn("plone.typesense.upgrades", products)


if __name__ == "__main__":
    unittest.main()
