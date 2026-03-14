# -*- coding: utf-8 -*-
from unittest import mock

from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING
from plone.typesense.views.typesense_sync import ITypesenseSync
from plone.typesense.views.typesense_sync import TypesenseSync
from zope.component import getMultiAdapter

import unittest


class TestTypesenseSyncViewRegistration(unittest.TestCase):
    """Test the sync view is properly registered."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_sync_view_is_registered(self):
        view = getMultiAdapter(
            (self.portal, self.portal.REQUEST),
            name="typesense-sync",
        )
        self.assertTrue(ITypesenseSync.providedBy(view))

    def test_sync_view_instance(self):
        view = getMultiAdapter(
            (self.portal, self.portal.REQUEST),
            name="typesense-sync",
        )
        self.assertIsInstance(view, TypesenseSync)


class TestTypesenseSyncViewLogic(unittest.TestCase):
    """Test the sync view logic with mocked Typesense."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        # Create some test content
        self.doc1 = api.content.create(
            self.portal, "Document", "doc1", title="Document 1"
        )
        self.doc2 = api.content.create(
            self.portal, "Document", "doc2", title="Document 2"
        )

    def _make_view(self):
        view = getMultiAdapter(
            (self.portal, self.portal.REQUEST),
            name="typesense-sync",
        )
        return view

    def test_get_catalog_uids(self):
        """Test that catalog UIDs are properly retrieved."""
        view = self._make_view()
        uids = view._get_catalog_uids()
        self.assertIsInstance(uids, set)
        # Should contain UIDs for our test documents
        doc1_uid = api.content.get_uuid(self.doc1)
        doc2_uid = api.content.get_uuid(self.doc2)
        self.assertIn(doc1_uid, uids)
        self.assertIn(doc2_uid, uids)

    def test_get_typesense_uids_empty(self):
        """Test retrieval of Typesense UIDs when collection is empty."""
        view = self._make_view()
        mock_client = mock.MagicMock()
        mock_client.collections.__getitem__().documents.search.return_value = {
            "hits": [],
            "found": 0,
        }
        mock_connector = mock.MagicMock()
        mock_connector.get_client.return_value = mock_client
        mock_connector.collection_base_name = "test_collection"

        uids = view._get_typesense_uids(mock_connector)
        self.assertEqual(uids, set())

    def test_get_typesense_uids_with_documents(self):
        """Test retrieval of Typesense UIDs with existing documents."""
        view = self._make_view()
        mock_client = mock.MagicMock()
        mock_client.collections.__getitem__().documents.search.return_value = {
            "hits": [
                {"document": {"id": "uid-1"}},
                {"document": {"id": "uid-2"}},
                {"document": {"id": "uid-3"}},
            ],
            "found": 3,
        }
        mock_connector = mock.MagicMock()
        mock_connector.get_client.return_value = mock_client
        mock_connector.collection_base_name = "test_collection"

        uids = view._get_typesense_uids(mock_connector)
        self.assertEqual(uids, {"uid-1", "uid-2", "uid-3"})

    def test_delete_orphan_documents(self):
        """Test deletion of orphan documents from Typesense."""
        view = self._make_view()
        mock_client = mock.MagicMock()
        mock_connector = mock.MagicMock()
        mock_connector.get_client.return_value = mock_client
        mock_connector.collection_base_name = "test_collection"

        orphan_uids = {"orphan-1", "orphan-2"}
        deleted = view._delete_orphan_documents(orphan_uids, mock_connector)

        self.assertEqual(deleted, 2)
        # Verify delete was called for each orphan
        self.assertEqual(
            mock_client.collections.__getitem__().documents.__getitem__().delete.call_count,
            2,
        )

    def test_delete_orphan_documents_handles_errors(self):
        """Test that deletion gracefully handles errors."""
        view = self._make_view()
        mock_client = mock.MagicMock()
        mock_client.collections.__getitem__().documents.__getitem__().delete.side_effect = Exception(
            "Not found"
        )
        mock_connector = mock.MagicMock()
        mock_connector.get_client.return_value = mock_client
        mock_connector.collection_base_name = "test_collection"

        orphan_uids = {"orphan-1"}
        deleted = view._delete_orphan_documents(orphan_uids, mock_connector)
        self.assertEqual(deleted, 0)

    @mock.patch(
        "plone.typesense.views.typesense_sync.getUtility"
    )
    def test_synchronize_all_in_sync(self, mock_get_utility):
        """Test synchronize when catalog and Typesense are already in sync."""
        view = self._make_view()
        catalog_uids = view._get_catalog_uids()

        mock_client = mock.MagicMock()
        # Return the same UIDs from Typesense as from catalog
        hits = [{"document": {"id": uid}} for uid in catalog_uids]
        mock_client.collections.__getitem__().documents.search.return_value = {
            "hits": hits,
            "found": len(hits),
        }
        mock_connector = mock.MagicMock()
        mock_connector.get_client.return_value = mock_client
        mock_connector.collection_base_name = "test_collection"
        mock_get_utility.return_value = mock_connector

        results = view._synchronize()

        self.assertEqual(results["missing"], 0)
        self.assertEqual(results["orphans"], 0)
        self.assertEqual(results["indexed"], 0)
        self.assertEqual(results["deleted"], 0)

    @mock.patch(
        "plone.typesense.views.typesense_sync.getUtility"
    )
    def test_synchronize_finds_orphans(self, mock_get_utility):
        """Test synchronize detects orphan documents in Typesense."""
        view = self._make_view()
        catalog_uids = view._get_catalog_uids()

        # Add extra UIDs to Typesense that are not in catalog
        all_uids = list(catalog_uids) + ["orphan-uid-1", "orphan-uid-2"]
        hits = [{"document": {"id": uid}} for uid in all_uids]
        mock_client = mock.MagicMock()
        mock_client.collections.__getitem__().documents.search.return_value = {
            "hits": hits,
            "found": len(hits),
        }
        mock_connector = mock.MagicMock()
        mock_connector.get_client.return_value = mock_client
        mock_connector.collection_base_name = "test_collection"
        mock_get_utility.return_value = mock_connector

        results = view._synchronize()

        self.assertEqual(results["orphans"], 2)
        self.assertEqual(results["deleted"], 2)
        self.assertEqual(results["missing"], 0)
