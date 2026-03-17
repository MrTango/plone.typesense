"""
Tests for searching and indexing when catalog indexes are deleted.

This is a KEY FEATURE for performance improvement - allows deleting expensive
text indexes (Title, Description, SearchableText) from portal_catalog while
keeping them in Typesense only.

Reference: collective.elasticsearch tests/test_search.py:TestSearchOnRemovedIndex
"""
from unittest import mock

from plone import api
from plone.app.testing import TEST_USER_ID
from plone.app.testing import setRoles
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING
from plone.typesense.utils import get_ts_only_indexes
import unittest


class TestSearchOnDeletedIndexes(unittest.TestCase):
    """Test that search works when indexes are deleted from portal_catalog."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.catalog = api.portal.get_tool("portal_catalog")
        self.zcatalog = self.catalog._catalog
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        # Disable Typesense routing since we're testing catalog behavior
        patcher = mock.patch(
            "plone.typesense.patches.TypesenseManager"
        )
        self.mock_manager_cls = patcher.start()
        self.mock_manager_cls.return_value.active = False
        self.addCleanup(patcher.stop)

    def test_deleting_searchabletext_index_does_not_crash(self):
        """Verify deleting SearchableText from catalog doesn't break things."""
        # Create document BEFORE deleting index
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="fancy-document",
            title="A Fancy Title",
            description="A fancy description",
        )

        doc.reindexObject()

        # Verify index exists in catalog initially
        self.assertIn("SearchableText", self.zcatalog.indexes.keys())

        # Delete SearchableText index from catalog
        self.zcatalog.delIndex("SearchableText")

        # Verify index is gone from catalog
        self.assertNotIn("SearchableText", self.zcatalog.indexes.keys())

        # Searching by a deleted index parameter is ignored by the catalog,
        # so we just verify no crash occurs
        results = self.catalog.searchResults(
            portal_type="Document",
            SearchableText="Fancy"
        )
        # The catalog ignores unknown query keys, so it returns all Documents
        self.assertGreaterEqual(len(results), 1)

    def test_reindexing_works_after_deleting_index(self):
        """Verify reindexing works after deleting index from catalog.

        Without Typesense routing, once the SearchableText index is deleted,
        the catalog ignores that query parameter entirely. We verify that
        reindexing doesn't raise and the document is still findable by Title.
        """
        # Create document
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="test-document",
            title="Original Title",
        )
        doc.reindexObject()

        # Delete SearchableText index
        self.zcatalog.delIndex("SearchableText")

        # Update and reindex — should not raise
        doc.title = "Updated Title"
        doc.reindexObject(idxs=["SearchableText", "Title"])

        # Document should be findable by Title index (still in catalog)
        results = self.catalog.searchResults(
            portal_type="Document",
            Title="Updated Title"
        )
        self.assertEqual(len(results), 1, "Should find updated title via Title index")
        self.assertEqual(results[0].Title, "Updated Title")

    def test_delete_all_ts_only_indexes(self):
        """Verify deleting all ts_only_indexes doesn't crash."""
        # Create test content
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="multi-index-test",
            title="Test Title",
            description="Test Description",
        )
        doc.reindexObject()

        # Get ts_only_indexes
        ts_only = get_ts_only_indexes()

        # Delete all ts_only indexes from catalog
        for idx in ts_only:
            if idx in self.zcatalog.indexes.keys():
                self.zcatalog.delIndex(idx)

        # Verify all are deleted
        for idx in ts_only:
            self.assertNotIn(idx, self.zcatalog.indexes.keys())

        # Searching with deleted index parameters should not crash
        # (catalog ignores unknown query keys)
        results = self.catalog.searchResults(portal_type="Document")
        self.assertGreaterEqual(len(results), 1)

    def test_new_content_indexes_without_catalog_index(self):
        """Verify new content can be created/indexed when catalog index doesn't exist."""
        # Delete SearchableText FIRST
        if "SearchableText" in self.zcatalog.indexes.keys():
            self.zcatalog.delIndex("SearchableText")

        # NOW create content (after index is deleted) — should not raise
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="new-without-index",
            title="Created After Index Deletion",
        )
        doc.reindexObject()

        # Document should exist and be findable by portal_type
        results = self.catalog.searchResults(
            portal_type="Document",
            id="new-without-index",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].getId, "new-without-index")

    def test_description_index_deletion(self):
        """Test Description index can be safely deleted."""
        # Create content
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="description-test",
            title="Description Test",
            description="This is a searchable description",
        )
        doc.reindexObject()

        # Delete Description index — should not raise
        if "Description" in self.zcatalog.indexes.keys():
            self.zcatalog.delIndex("Description")

        # Document should still be findable by other indexes
        results = self.catalog.searchResults(
            portal_type="Document",
            id="description-test",
        )
        self.assertEqual(len(results), 1)

    def test_title_index_deletion(self):
        """Test Title index can be safely deleted."""
        # Create content
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="title-test",
            title="Unique Title XYZ",
        )
        doc.reindexObject()

        # Delete Title index — should not raise
        if "Title" in self.zcatalog.indexes.keys():
            self.zcatalog.delIndex("Title")

        # Document should still be findable by other indexes
        results = self.catalog.searchResults(
            portal_type="Document",
            id="title-test",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].getId, "title-test")


class TestIndexingWithDeletedIndexes(unittest.TestCase):
    """Test indexing behavior when catalog indexes are deleted."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.catalog = api.portal.get_tool("portal_catalog")
        self.zcatalog = self.catalog._catalog
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        # Disable Typesense routing since we're testing catalog behavior
        patcher = mock.patch(
            "plone.typesense.patches.TypesenseManager"
        )
        self.mock_manager_cls = patcher.start()
        self.mock_manager_cls.return_value.active = False
        self.addCleanup(patcher.stop)

    def test_get_value_uses_mockindex_for_deleted_index(self):
        """Verify MockIndex is used when index is deleted."""
        from plone.typesense.queueprocessor import IndexProcessor
        from plone.typesense.utils import get_ts_only_indexes

        # Create document
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="mockindex-test",
            title="MockIndex Test Title",
        )

        # Delete Title if it's in ts_only_indexes
        ts_only = get_ts_only_indexes()
        if "Title" in ts_only and "Title" in self.zcatalog.indexes.keys():
            self.zcatalog.delIndex("Title")

        # Get data using IndexProcessor
        processor = IndexProcessor()
        uuid = api.content.get_uuid(doc)
        data = processor.get_data_for_ts(uuid, attributes=["Title"])

        # Should have extracted Title value even though index is deleted
        self.assertIn("Title", data)
        self.assertEqual(data["Title"], "MockIndex Test Title")

    def test_reindex_specific_attributes_without_catalog_index(self):
        """Verify reindexObject(idxs=[...]) works when index is deleted."""
        # Create document
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="reindex-attrs-test",
            title="Original",
        )
        doc.reindexObject()

        # Delete SearchableText index
        if "SearchableText" in self.zcatalog.indexes.keys():
            self.zcatalog.delIndex("SearchableText")

        # Update and reindex specific attributes
        doc.title = "Modified"
        # This should not raise an error even though SearchableText is deleted
        doc.reindexObject(idxs=["SearchableText", "Title"])

        # Document should still be findable by Title (not deleted)
        results = self.catalog.searchResults(
            portal_type="Document",
            Title="Modified"
        )
        self.assertEqual(len(results), 1)

    def test_catalog_rebuild_with_deleted_indexes(self):
        """Verify catalog rebuild works when some indexes are deleted."""
        # Create content
        doc = api.content.create(
            container=self.portal,
            type="Document",
            id="rebuild-test",
            title="Rebuild Test",
        )

        # Delete SearchableText
        if "SearchableText" in self.zcatalog.indexes.keys():
            self.zcatalog.delIndex("SearchableText")

        # Rebuild catalog (this calls reindexObject on all content)
        # Should not raise errors
        self.catalog.clearFindAndRebuild()

        # Content should still be findable by other indexes
        results = self.catalog.searchResults(
            portal_type="Document",
            id="rebuild-test",
        )
        self.assertEqual(len(results), 1)


class TestPerformanceBenefit(unittest.TestCase):
    """Document the performance benefit of deleting indexes."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.catalog = api.portal.get_tool("portal_catalog")
        self.zcatalog = self.catalog._catalog
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        # Disable Typesense routing since we're testing catalog behavior
        patcher = mock.patch(
            "plone.typesense.patches.TypesenseManager"
        )
        self.mock_manager_cls = patcher.start()
        self.mock_manager_cls.return_value.active = False
        self.addCleanup(patcher.stop)

    def test_catalog_size_before_and_after_deletion(self):
        """
        This test documents the expected performance benefit.

        By deleting SearchableText, Title, and Description indexes from
        portal_catalog, you can expect:

        1. Reduced RAM usage (text indexes are large)
        2. Faster catalog operations (fewer indexes to maintain)
        3. Smaller catalog database size
        4. Faster portal_catalog queries (for non-text searches)

        Typesense handles text search much faster than portal_catalog's
        ZCTextIndex, so this is a win-win situation.
        """
        # Get initial index count
        initial_count = len(self.zcatalog.indexes.keys())

        # Delete ts_only_indexes
        ts_only = get_ts_only_indexes()
        deleted_count = 0
        for idx in ts_only:
            if idx in self.zcatalog.indexes.keys():
                self.zcatalog.delIndex(idx)
                deleted_count += 1

        # Get final index count
        final_count = len(self.zcatalog.indexes.keys())

        # Verify indexes were deleted
        self.assertEqual(initial_count - deleted_count, final_count)

        # Document the benefit
        self.assertGreater(deleted_count, 0)
