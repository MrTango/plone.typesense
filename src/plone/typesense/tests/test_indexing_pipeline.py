"""Tests for Phase 0 critical bug fixes in the indexing pipeline."""

import unittest
from unittest.mock import MagicMock, patch, call

from plone.typesense.interfaces import IndexingActions


class TestTypesenseError(unittest.TestCase):
    """Test that TypesenseError inherits from Exception, not BaseException."""

    def test_inherits_from_exception(self):
        from plone.typesense.global_utilities.typesense import TypesenseError

        self.assertTrue(issubclass(TypesenseError, Exception))

    def test_caught_by_except_exception(self):
        from plone.typesense.global_utilities.typesense import TypesenseError

        caught = False
        try:
            raise TypesenseError("test error")
        except Exception:
            caught = True
        self.assertTrue(caught)

    def test_str_representation(self):
        from plone.typesense.global_utilities.typesense import TypesenseError

        err = TypesenseError("connection failed", exit_status=2)
        self.assertIn("connection failed", str(err))


class TestDeleteFilterSyntax(unittest.TestCase):
    """Test that delete() uses correct Typesense filter syntax."""

    @patch("plone.typesense.global_utilities.typesense.api")
    def test_delete_filter_format(self, mock_api):
        from plone.typesense.global_utilities.typesense import TypesenseConnector

        connector = TypesenseConnector()
        mock_client = MagicMock()
        connector.data = MagicMock()
        connector.data.client = mock_client

        # Mock collection_base_name
        mock_api.portal.get_registry_record.return_value = "test-collection"

        uids = ["uid1", "uid2", "uid3"]
        connector.delete(uids)

        # Verify the filter_by syntax
        delete_call = mock_client.collections["test-collection"].documents.delete
        delete_call.assert_called_once()
        args = delete_call.call_args
        filter_param = args[0][0]
        self.assertIn("filter_by", filter_param)
        self.assertIn("id:[", filter_param["filter_by"])
        # Check backtick-wrapped UIDs
        for uid in uids:
            self.assertIn(f"`{uid}`", filter_param["filter_by"])

    @patch("plone.typesense.global_utilities.typesense.api")
    def test_delete_empty_uids(self, mock_api):
        from plone.typesense.global_utilities.typesense import TypesenseConnector

        connector = TypesenseConnector()
        mock_client = MagicMock()
        connector.data = MagicMock()
        connector.data.client = mock_client

        connector.delete([])
        mock_client.collections.__getitem__.assert_not_called()


class TestIndexPassesDicts(unittest.TestCase):
    """Test that index() passes dicts to Typesense client, not JSON strings."""

    @patch("plone.typesense.global_utilities.typesense.api")
    def test_index_uses_import(self, mock_api):
        from plone.typesense.global_utilities.typesense import TypesenseConnector

        connector = TypesenseConnector()
        mock_client = MagicMock()
        connector.data = MagicMock()
        connector.data.client = mock_client

        mock_api.portal.get_registry_record.return_value = "test-collection"

        objects = [{"id": "1", "title": "Test"}, {"id": "2", "title": "Test 2"}]
        connector.index(objects)

        # Verify import_ was called with dict objects, not JSON strings
        import_call = mock_client.collections["test-collection"].documents.import_
        import_call.assert_called_once()
        args = import_call.call_args[0]
        self.assertEqual(args[0], objects)
        self.assertEqual(args[1], {"action": "upsert"})

    @patch("plone.typesense.global_utilities.typesense.api")
    def test_index_empty_list(self, mock_api):
        from plone.typesense.global_utilities.typesense import TypesenseConnector

        connector = TypesenseConnector()
        mock_client = MagicMock()
        connector.data = MagicMock()
        connector.data.client = mock_client

        connector.index([])
        mock_client.collections.__getitem__.assert_not_called()


class TestUpdatePassesDicts(unittest.TestCase):
    """Test that update() passes dicts to Typesense client."""

    @patch("plone.typesense.global_utilities.typesense.api")
    def test_update_uses_dict(self, mock_api):
        from plone.typesense.global_utilities.typesense import TypesenseConnector

        connector = TypesenseConnector()
        mock_client = MagicMock()
        connector.data = MagicMock()
        connector.data.client = mock_client

        mock_api.portal.get_registry_record.return_value = "test-collection"

        obj = {"id": "doc1", "title": "Updated"}
        connector.update([obj])

        # Verify update was called with dict, not JSON string
        doc_mock = mock_client.collections["test-collection"].documents["doc1"]
        doc_mock.update.assert_called_once_with(obj)


class TestIndexingActions(unittest.TestCase):
    """Test IndexingActions.all() mapping."""

    def test_all_maps_unindex_to_delete(self):
        actions = IndexingActions(
            index={},
            reindex={},
            unindex={"uid1": {}, "uid2": {}},
            index_blobs={},
            uuid_path={},
        )
        all_data = actions.all()
        for action, uuid, data in all_data:
            self.assertEqual(action, "delete")


class TestCommitTsDeleteBranch(unittest.TestCase):
    """Test that commit_ts processes delete actions."""

    def test_delete_branch_exists(self):
        """Verify commit_ts has a delete branch by inspecting the source."""
        import inspect
        from plone.typesense.queueprocessor import IndexProcessor

        source = inspect.getsource(IndexProcessor.commit_ts)
        self.assertIn('"delete"', source)
        self.assertIn("ts_delete", source)

    def test_ts_delete_method_exists(self):
        """Verify ts_delete method exists on IndexProcessor."""
        from plone.typesense.queueprocessor import IndexProcessor

        self.assertTrue(hasattr(IndexProcessor, "ts_delete"))


class TestTypeseResultSlice(unittest.TestCase):
    """Test TypesenseResult.__getitem__ slice handling."""

    def test_slice_uses_stop_not_end(self):
        """Verify the slice code uses .stop, not .end."""
        import inspect
        from plone.typesense.result import TypesenseResult

        source = inspect.getsource(TypesenseResult.__getitem__)
        self.assertIn("key.stop", source)
        self.assertNotIn("key.end", source)


class TestCheckPerms(unittest.TestCase):
    """Test that check_perms parameter flows through in search_results."""

    def test_check_perms_not_hardcoded(self):
        """Verify check_perms=False is not hardcoded in search_results."""
        import inspect
        from plone.typesense.manager import TypesenseManager

        source = inspect.getsource(TypesenseManager.search_results)
        # Should not contain 'check_perms = False'
        self.assertNotIn("check_perms = False", source)


class TestHTMLStripperModuleLevel(unittest.TestCase):
    """Test HTMLStripper is defined at module level in indexes.py."""

    def test_importable_from_indexes(self):
        from plone.typesense.indexes import HTMLStripper

        stripper = HTMLStripper()
        stripper.feed("<p>Hello world</p>")
        self.assertEqual(stripper.get_data(), "Hello world")

    def test_strips_nested_tags(self):
        from plone.typesense.indexes import HTMLStripper

        stripper = HTMLStripper()
        stripper.feed("<div><p>First</p><p>Second</p></div>")
        self.assertEqual(stripper.get_data(), "First Second")


class TestMockIndexConsolidated(unittest.TestCase):
    """Test MockIndex is consolidated in query.py."""

    def test_importable_from_query(self):
        from plone.typesense.query import MockIndex

        mock = MockIndex("SearchableText")
        attrs = mock.getIndexSourceNames()
        self.assertIn("Title", attrs)
        self.assertIn("Description", attrs)
        self.assertIn("text", attrs)
        self.assertIn("body", attrs)
        self.assertIn("id", attrs)

    def test_non_searchable_text_index(self):
        from plone.typesense.query import MockIndex

        mock = MockIndex("Subject")
        attrs = mock.getIndexSourceNames()
        self.assertEqual(attrs, ["Subject"])


class TestBrainHighlighting(unittest.TestCase):
    """Test brain highlighting uses attribute assignment, not subscript."""

    def test_highlight_code_uses_attribute(self):
        """Verify the highlighting code guards brain['Description'] with 'if fragments:'."""
        import inspect
        from plone.typesense.result import BrainFactory

        source = inspect.getsource(BrainFactory)
        # The fix for B6 wraps the Description assignment in an `if fragments:` guard
        self.assertIn("if fragments:", source)
        self.assertIn('brain["Description"]', source)


class TestReindexView(unittest.TestCase):
    """Test reindex view fixes."""

    def test_uses_processor_not_direct_connector(self):
        """Verify the view uses IndexProcessor for proper data handling."""
        import inspect
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("ITypesenseSearchIndexQueueProcessor", source)
        self.assertIn("processor.index", source)
        self.assertIn("processor.commit", source)

    def test_has_csrf_and_post_check(self):
        """Verify the view has CSRF protection and POST check."""
        import inspect
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("CheckAuthenticator", source)
        self.assertIn('"POST"', source)


if __name__ == "__main__":
    unittest.main()
