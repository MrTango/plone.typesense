"""Tests for upgrade steps."""
import unittest
from unittest import mock

from plone.typesense import upgrades


class TestReloadProfile(unittest.TestCase):
    """Test the reload_profile upgrade step."""

    def test_runs_all_import_steps(self):
        context = mock.Mock()
        with mock.patch("plone.typesense.upgrades.log"):
            upgrades.reload_profile(context)
        context.runAllImportStepsFromProfile.assert_called_once_with(
            "profile-plone.typesense:default"
        )


class TestUpgradeTo2(unittest.TestCase):
    """Test the upgrade_to_2 upgrade step."""

    def test_reimports_registry(self):
        context = mock.Mock()
        with mock.patch("plone.typesense.upgrades.log"):
            upgrades.upgrade_to_2(context)
        context.runImportStepFromProfile.assert_called_once_with(
            "profile-plone.typesense:default", "plone.app.registry"
        )


if __name__ == "__main__":
    unittest.main()
