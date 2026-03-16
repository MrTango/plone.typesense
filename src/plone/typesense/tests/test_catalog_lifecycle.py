"""Tests for Phase 1: Catalog Lifecycle — Keep Typesense in sync."""

import inspect
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from plone.typesense.interfaces import IndexingActions


def _make_actions():
    """Create a fresh IndexingActions instance."""
    return IndexingActions(
        index={},
        reindex={},
        unindex={},
        index_blobs={},
        uuid_path={},
    )


class TestIReindexActiveInterface(unittest.TestCase):
    """Test IReindexActive marker interface."""

    def test_interface_importable(self):
        from plone.typesense.interfaces import IReindexActive
        from zope.interface import Interface

        self.assertTrue(issubclass(IReindexActive, Interface))

    def test_can_be_provided(self):
        from plone.typesense.interfaces import IReindexActive
        from zope.interface import alsoProvides, implementer

        mock_request = MagicMock()
        alsoProvides(mock_request, IReindexActive)
        self.assertTrue(IReindexActive.providedBy(mock_request))

    def test_can_be_removed(self):
        from plone.typesense.interfaces import IReindexActive
        from zope.interface import alsoProvides, noLongerProvides

        mock_request = MagicMock()
        alsoProvides(mock_request, IReindexActive)
        noLongerProvides(mock_request, IReindexActive)
        self.assertFalse(IReindexActive.providedBy(mock_request))


class TestIAdditionalIndexDataProviderInterface(unittest.TestCase):
    """Test IAdditionalIndexDataProvider interface."""

    def test_interface_importable(self):
        from plone.typesense.interfaces import IAdditionalIndexDataProvider
        from zope.interface import Interface

        self.assertTrue(issubclass(IAdditionalIndexDataProvider, Interface))


class TestRebuildProperty(unittest.TestCase):
    """Test that IndexProcessor.rebuild checks IReindexActive marker."""

    def test_rebuild_uses_ireindex_active(self):
        """Verify rebuild property checks IReindexActive on the request."""
        from plone.typesense.queueprocessor import IndexProcessor

        source = inspect.getsource(IndexProcessor.rebuild.fget)
        self.assertIn("IReindexActive", source)
        self.assertIn("getRequest", source)

    def test_rebuild_returns_false_when_inactive(self):
        from plone.typesense.queueprocessor import IndexProcessor

        processor = IndexProcessor()
        with patch.object(
            type(processor), "active", new_callable=PropertyMock, return_value=False
        ):
            self.assertFalse(processor.rebuild)

    @patch("plone.typesense.queueprocessor.api")
    def test_rebuild_returns_true_with_marker(self, mock_api):
        from plone.typesense.interfaces import IReindexActive
        from plone.typesense.queueprocessor import IndexProcessor
        from zope.interface import alsoProvides

        processor = IndexProcessor()
        mock_request = MagicMock()
        alsoProvides(mock_request, IReindexActive)

        with patch.object(
            type(processor), "active", new_callable=PropertyMock, return_value=True
        ):
            with patch(
                "zope.globalrequest.getRequest", return_value=mock_request
            ):
                self.assertTrue(processor.rebuild)

    @patch("plone.typesense.queueprocessor.api")
    def test_rebuild_returns_false_without_marker(self, mock_api):
        from plone.typesense.queueprocessor import IndexProcessor

        processor = IndexProcessor()
        mock_request = MagicMock()

        with patch.object(
            type(processor), "active", new_callable=PropertyMock, return_value=True
        ):
            with patch(
                "zope.globalrequest.getRequest", return_value=mock_request
            ):
                self.assertFalse(processor.rebuild)


class TestAdditionalIndexDataProviderWiring(unittest.TestCase):
    """Test IAdditionalIndexDataProvider is wired in get_data_for_ts."""

    def test_adapter_lookup_in_source(self):
        from plone.typesense.queueprocessor import IndexProcessor

        source = inspect.getsource(IndexProcessor.get_data_for_ts)
        self.assertIn("getAdapters", source)
        self.assertIn("IAdditionalIndexDataProvider", source)

    def test_adapter_import_exists(self):
        """Verify IAdditionalIndexDataProvider is imported in queueprocessor."""
        import plone.typesense.queueprocessor as mod

        self.assertTrue(hasattr(mod, "IAdditionalIndexDataProvider"))


class TestEventSubscriberObjectAdded(unittest.TestCase):
    """Test object_added subscriber."""

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_calls_processor_index(self, mock_query):
        from plone.typesense.subscribers.index_in_typesense import object_added

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.newParent = MagicMock()  # set (real add)
        event.oldParent = None  # not set (not a move)

        object_added(obj, event)
        mock_processor.index.assert_called_once_with(obj)

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_skips_when_inactive(self, mock_query):
        from plone.typesense.subscribers.index_in_typesense import object_added

        mock_processor = MagicMock()
        mock_processor.active = False
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.newParent = MagicMock()
        event.oldParent = None

        object_added(obj, event)
        mock_processor.index.assert_not_called()

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_skips_on_move(self, mock_query):
        """When oldParent is set, it's a move — object_added should skip."""
        from plone.typesense.subscribers.index_in_typesense import object_added

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.newParent = MagicMock()
        event.oldParent = MagicMock()  # both set = move

        object_added(obj, event)
        mock_processor.index.assert_not_called()


class TestEventSubscriberObjectModified(unittest.TestCase):
    """Test object_modified subscriber."""

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_calls_processor_reindex(self, mock_query):
        from plone.typesense.subscribers.index_in_typesense import object_modified

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock(spec=[])  # no descriptions attribute

        object_modified(obj, event)
        mock_processor.reindex.assert_called_once_with(obj)

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_extracts_attributes_from_descriptions(self, mock_query):
        from plone.typesense.subscribers.index_in_typesense import object_modified

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        desc = MagicMock()
        desc.attributes = ("title", "description")
        event = MagicMock()
        event.descriptions = [desc]

        object_modified(obj, event)
        mock_processor.reindex.assert_called_once()
        call_kwargs = mock_processor.reindex.call_args
        attrs = call_kwargs[1].get("attributes") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("attributes")
        self.assertIn("title", attrs)
        self.assertIn("description", attrs)


class TestEventSubscriberObjectRemoved(unittest.TestCase):
    """Test object_removed subscriber."""

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_calls_processor_unindex(self, mock_query):
        from plone.typesense.subscribers.index_in_typesense import object_removed

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.newParent = None  # real delete

        object_removed(obj, event)
        mock_processor.unindex.assert_called_once_with(obj)

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_skips_on_move(self, mock_query):
        """When newParent is set, it's a move — object_removed should skip."""
        from plone.typesense.subscribers.index_in_typesense import object_removed

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.newParent = MagicMock()  # has newParent = move

        object_removed(obj, event)
        mock_processor.unindex.assert_not_called()


class TestEventSubscriberObjectMoved(unittest.TestCase):
    """Test object_moved subscriber."""

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_calls_reindex_on_genuine_move(self, mock_query):
        from plone.typesense.subscribers.index_in_typesense import object_moved

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.oldParent = MagicMock()
        event.newParent = MagicMock()

        object_moved(obj, event)
        mock_processor.reindex.assert_called_once_with(obj)

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_skips_on_add(self, mock_query):
        """oldParent=None means add, not move."""
        from plone.typesense.subscribers.index_in_typesense import object_moved

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.oldParent = None
        event.newParent = MagicMock()

        object_moved(obj, event)
        mock_processor.reindex.assert_not_called()

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_skips_on_delete(self, mock_query):
        """newParent=None means delete, not move."""
        from plone.typesense.subscribers.index_in_typesense import object_moved

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.oldParent = MagicMock()
        event.newParent = None

        object_moved(obj, event)
        mock_processor.reindex.assert_not_called()


class TestEventSubscriberWorkflowChanged(unittest.TestCase):
    """Test object_workflow_changed subscriber."""

    @patch("plone.typesense.subscribers.index_in_typesense.queryUtility")
    def test_reindexes_review_state_and_permissions(self, mock_query):
        from plone.typesense.subscribers.index_in_typesense import (
            object_workflow_changed,
        )

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_query.return_value = mock_processor

        obj = MagicMock()
        event = MagicMock()
        event.action = "publish"

        object_workflow_changed(obj, event)
        mock_processor.reindex.assert_called_once()
        call_kwargs = mock_processor.reindex.call_args[1]
        self.assertIn("review_state", call_kwargs["attributes"])
        self.assertIn("allowedRolesAndUsers", call_kwargs["attributes"])


class TestUncatalogObjectPatch(unittest.TestCase):
    """Test uncatalog_object patch queues Typesense delete."""

    def test_source_extracts_uid_before_original(self):
        """Verify UUID is extracted before calling the original method."""
        from plone.typesense.patches import uncatalog_object

        source = inspect.getsource(uncatalog_object)
        # UUID extraction should come before _old_uncatalog_object call
        uid_extraction_pos = source.find("getMetadataForRID")
        original_call_pos = source.find("_old_uncatalog_object")
        self.assertGreater(original_call_pos, uid_extraction_pos)

    def test_source_queues_delete(self):
        from plone.typesense.patches import uncatalog_object

        source = inspect.getsource(uncatalog_object)
        self.assertIn("actions.unindex", source)

    @patch("plone.typesense.patches.queryUtility")
    def test_queues_ts_delete(self, mock_query):
        from plone.typesense.patches import uncatalog_object

        actions = _make_actions()
        mock_processor = MagicMock()
        mock_processor.active = True
        mock_processor.actions = actions
        mock_query.return_value = mock_processor

        mock_catalog = MagicMock()
        mock_catalog._catalog.uids.get.return_value = 42
        mock_catalog._catalog.getMetadataForRID.return_value = {"UID": "test-uuid-123"}
        mock_catalog._old_uncatalog_object = MagicMock()

        uncatalog_object(mock_catalog, "/plone/my-page")

        mock_catalog._old_uncatalog_object.assert_called_once_with("/plone/my-page")
        self.assertIn("test-uuid-123", actions.unindex)

    @patch("plone.typesense.patches.queryUtility")
    def test_removes_from_index_and_reindex_queues(self, mock_query):
        from plone.typesense.patches import uncatalog_object

        actions = _make_actions()
        actions.index["test-uuid-123"] = {"title": "Test"}
        actions.reindex["test-uuid-123"] = {"title": "Test"}

        mock_processor = MagicMock()
        mock_processor.active = True
        mock_processor.actions = actions
        mock_query.return_value = mock_processor

        mock_catalog = MagicMock()
        mock_catalog._catalog.uids.get.return_value = 42
        mock_catalog._catalog.getMetadataForRID.return_value = {"UID": "test-uuid-123"}
        mock_catalog._old_uncatalog_object = MagicMock()

        uncatalog_object(mock_catalog, "/plone/my-page")

        self.assertNotIn("test-uuid-123", actions.index)
        self.assertNotIn("test-uuid-123", actions.reindex)
        self.assertIn("test-uuid-123", actions.unindex)

    @patch("plone.typesense.patches.queryUtility")
    def test_skips_when_inactive(self, mock_query):
        from plone.typesense.patches import uncatalog_object

        mock_processor = MagicMock()
        mock_processor.active = False
        mock_query.return_value = mock_processor

        mock_catalog = MagicMock()
        mock_catalog._old_uncatalog_object = MagicMock()

        uncatalog_object(mock_catalog, "/plone/my-page")

        mock_catalog._old_uncatalog_object.assert_called_once()


class TestManageCatalogRebuildPatch(unittest.TestCase):
    """Test manage_catalogRebuild patch."""

    def test_source_clears_ts(self):
        from plone.typesense.patches import manage_catalogRebuild

        source = inspect.getsource(manage_catalogRebuild)
        self.assertIn("ts_connector.clear()", source)

    def test_source_sets_ireindex_active(self):
        from plone.typesense.patches import manage_catalogRebuild

        source = inspect.getsource(manage_catalogRebuild)
        self.assertIn("IReindexActive", source)
        self.assertIn("alsoProvides", source)

    def test_source_removes_marker_in_finally(self):
        from plone.typesense.patches import manage_catalogRebuild

        source = inspect.getsource(manage_catalogRebuild)
        self.assertIn("finally", source)
        self.assertIn("noLongerProvides", source)

    @patch("plone.typesense.patches.queryUtility")
    def test_clears_ts_and_calls_original(self, mock_query):
        from plone.typesense.patches import manage_catalogRebuild

        mock_connector = MagicMock()
        mock_processor = MagicMock()
        mock_processor.active = True
        mock_processor.ts_connector = mock_connector
        mock_query.return_value = mock_processor

        mock_catalog = MagicMock()
        mock_catalog._old_manage_catalogRebuild = MagicMock(return_value=None)

        with patch("zope.globalrequest.getRequest") as mock_get_request:
            mock_request = MagicMock()
            mock_get_request.return_value = mock_request
            manage_catalogRebuild(mock_catalog)

        mock_connector.clear.assert_called_once()
        mock_catalog._old_manage_catalogRebuild.assert_called_once()


class TestManageCatalogClearPatch(unittest.TestCase):
    """Test manage_catalogClear patch."""

    def test_source_clears_ts(self):
        from plone.typesense.patches import manage_catalogClear

        source = inspect.getsource(manage_catalogClear)
        self.assertIn("ts_connector.clear()", source)

    def test_source_calls_original(self):
        from plone.typesense.patches import manage_catalogClear

        source = inspect.getsource(manage_catalogClear)
        self.assertIn("_old_manage_catalogClear", source)

    @patch("plone.typesense.patches.queryUtility")
    def test_clears_ts_when_active(self, mock_query):
        from plone.typesense.patches import manage_catalogClear

        mock_connector = MagicMock()
        mock_processor = MagicMock()
        mock_processor.active = True
        mock_processor.ts_connector = mock_connector
        mock_query.return_value = mock_processor

        mock_catalog = MagicMock()
        mock_catalog._old_manage_catalogClear = MagicMock(return_value=None)

        manage_catalogClear(mock_catalog)

        mock_connector.clear.assert_called_once()
        mock_catalog._old_manage_catalogClear.assert_called_once()

    @patch("plone.typesense.patches.queryUtility")
    def test_skips_ts_when_inactive(self, mock_query):
        from plone.typesense.patches import manage_catalogClear

        mock_processor = MagicMock()
        mock_processor.active = False
        mock_query.return_value = mock_processor

        mock_catalog = MagicMock()
        mock_catalog._old_manage_catalogClear = MagicMock(return_value=None)

        manage_catalogClear(mock_catalog)

        mock_processor.ts_connector.clear.assert_not_called()
        mock_catalog._old_manage_catalogClear.assert_called_once()


class TestReindexView(unittest.TestCase):
    """Test reindex view rewrite."""

    def test_uses_index_processor(self):
        """Verify the view uses IndexProcessor, not direct ts_connector.index."""
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("ITypesenseSearchIndexQueueProcessor", source)
        self.assertNotIn("ts_connector.index", source)

    def test_has_csrf_protection(self):
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("CheckAuthenticator", source)

    def test_sets_ireindex_active(self):
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("IReindexActive", source)
        self.assertIn("alsoProvides", source)

    def test_removes_marker_in_finally(self):
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("finally", source)
        self.assertIn("noLongerProvides", source)

    def test_clears_ts_before_reindex(self):
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("ts_connector.clear()", source)

    def test_requires_post_method(self):
        from plone.typesense.views.typesense_reindex_collection import (
            TypesenseReindexCollection,
        )

        source = inspect.getsource(TypesenseReindexCollection.__call__)
        self.assertIn("request.method", source)
        self.assertIn('"POST"', source)


class TestReindexViewPermission(unittest.TestCase):
    """Test reindex view requires ManagePortal permission."""

    def test_zcml_permission(self):
        """Verify the ZCML registers with cmf.ManagePortal permission."""
        with open(
            "src/plone/typesense/views/configure.zcml", "r"
        ) as f:
            zcml_content = f.read()

        # Find the reindex-collection registration
        import re
        # Match the browser:page block for typesense-reindex-collection
        pattern = r'name="typesense-reindex-collection".*?permission="([^"]+)"'
        match = re.search(pattern, zcml_content, re.DOTALL)
        self.assertIsNotNone(match, "Could not find reindex-collection page registration")
        self.assertEqual(match.group(1), "cmf.ManagePortal")


class TestSubscriberZCML(unittest.TestCase):
    """Test subscriber ZCML registration."""

    def test_all_events_registered(self):
        with open(
            "src/plone/typesense/subscribers/configure.zcml", "r"
        ) as f:
            zcml_content = f.read()

        self.assertIn("IObjectAddedEvent", zcml_content)
        self.assertIn("IObjectModifiedEvent", zcml_content)
        self.assertIn("IObjectRemovedEvent", zcml_content)
        self.assertIn("IObjectMovedEvent", zcml_content)
        self.assertIn("IActionSucceededEvent", zcml_content)

    def test_correct_handlers(self):
        with open(
            "src/plone/typesense/subscribers/configure.zcml", "r"
        ) as f:
            zcml_content = f.read()

        self.assertIn("object_added", zcml_content)
        self.assertIn("object_modified", zcml_content)
        self.assertIn("object_removed", zcml_content)
        self.assertIn("object_moved", zcml_content)
        self.assertIn("object_workflow_changed", zcml_content)


class TestPatchesZCML(unittest.TestCase):
    """Test patches ZCML registration."""

    def test_all_patches_registered(self):
        with open(
            "src/plone/typesense/patches/configure.zcml", "r"
        ) as f:
            zcml_content = f.read()

        self.assertIn("uncatalog_object", zcml_content)
        self.assertIn("manage_catalogRebuild", zcml_content)
        self.assertIn("manage_catalogClear", zcml_content)

    def test_patches_preserve_original(self):
        with open(
            "src/plone/typesense/patches/configure.zcml", "r"
        ) as f:
            zcml_content = f.read()

        # All patches should preserve the original method
        self.assertEqual(zcml_content.count('preserveOriginal="True"'), 7)


if __name__ == "__main__":
    unittest.main()
