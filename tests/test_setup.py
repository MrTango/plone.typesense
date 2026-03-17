"""Test plone.typesense installation."""
import pytest

from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

from plone.typesense.testing import INTEGRATION_TESTING


class TestSetup:
    """Test installation and setup."""

    layer = INTEGRATION_TESTING

    @pytest.fixture(autouse=True)
    def _setup(self, integration_testing):
        self.portal = integration_testing["portal"]

    def test_addon_installed(self):
        """Test addon is installed."""
        installer = api.portal.get_tool("portal_quickinstaller")
        assert installer.isProductInstalled("plone.typesense")

    def test_browserlayer(self):
        """Test browserlayer is registered."""
        from plone.browserlayer import utils
        # Add actual browserlayer check if you have one
        # from plone.typesense.interfaces import IPloneTypesenseLayer
        # assert IPloneTypesenseLayer in utils.registered_layers()
        pass


class TestUninstall:
    """Test uninstallation."""

    layer = INTEGRATION_TESTING

    @pytest.fixture(autouse=True)
    def _setup(self, integration_testing):
        self.portal = integration_testing["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.installer = api.portal.get_tool("portal_quickinstaller")
        self.installer.uninstallProducts(["plone.typesense"])

    def test_addon_uninstalled(self):
        """Test addon is uninstalled."""
        assert not self.installer.isProductInstalled("plone.typesense")
