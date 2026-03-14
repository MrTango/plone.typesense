"""Tests for the moveObjectsByDelta monkey patch."""

import unittest
from unittest.mock import MagicMock, patch, call


class TestMoveObjectsByDeltaPatch(unittest.TestCase):
    """Test that moveObjectsByDelta queues Typesense reindex."""

    def _make_container(self, objects=None):
        """Create a mock container with _old_moveObjectsByDelta."""
        container = MagicMock()
        container._old_moveObjectsByDelta = MagicMock(return_value=1)
        if objects:
            container.get = lambda obj_id: objects.get(obj_id)
        else:
            container.get = MagicMock(return_value=None)
        return container

    @patch("plone.typesense.patches.TypesenseManager")
    @patch("Products.CMFCore.indexing.getQueue")
    def test_calls_original_method(self, mock_get_queue, mock_manager_cls):
        from plone.typesense.patches import moveObjectsByDelta

        mock_manager = MagicMock()
        mock_manager.active = False
        mock_manager_cls.return_value = mock_manager

        container = self._make_container()
        result = moveObjectsByDelta(container, ["item1"], 1)

        container._old_moveObjectsByDelta.assert_called_once_with(
            ["item1"], 1, subset_ids=None, suppress_events=False
        )
        self.assertEqual(result, 1)

    @patch("plone.typesense.patches.TypesenseManager")
    @patch("Products.CMFCore.indexing.getQueue")
    def test_skips_reindex_when_inactive(self, mock_get_queue, mock_manager_cls):
        from plone.typesense.patches import moveObjectsByDelta

        mock_manager = MagicMock()
        mock_manager.active = False
        mock_manager_cls.return_value = mock_manager

        container = self._make_container()
        moveObjectsByDelta(container, ["item1"], 1)

        # Queue should not be accessed when Typesense is inactive
        mock_get_queue.return_value.reindex.assert_not_called()

    @patch("plone.typesense.patches.TypesenseManager")
    @patch("Products.CMFCore.indexing.getQueue")
    def test_queues_reindex_when_active(self, mock_get_queue, mock_manager_cls):
        from plone.typesense.patches import moveObjectsByDelta

        mock_manager = MagicMock()
        mock_manager.active = True
        mock_manager_cls.return_value = mock_manager

        obj1 = MagicMock()
        obj2 = MagicMock()
        objects = {"item1": obj1, "item2": obj2}
        container = self._make_container(objects)

        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        moveObjectsByDelta(container, ["item1", "item2"], 1)

        # Both objects should be queued for reindex
        self.assertEqual(mock_queue.reindex.call_count, 2)
        mock_queue.reindex.assert_any_call(obj1, ["getObjPositionInParent"])
        mock_queue.reindex.assert_any_call(obj2, ["getObjPositionInParent"])

    @patch("plone.typesense.patches.TypesenseManager")
    @patch("Products.CMFCore.indexing.getQueue")
    def test_handles_string_id(self, mock_get_queue, mock_manager_cls):
        from plone.typesense.patches import moveObjectsByDelta

        mock_manager = MagicMock()
        mock_manager.active = True
        mock_manager_cls.return_value = mock_manager

        obj1 = MagicMock()
        objects = {"item1": obj1}
        container = self._make_container(objects)

        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        # Pass single string instead of list
        moveObjectsByDelta(container, "item1", 1)

        mock_queue.reindex.assert_called_once_with(
            obj1, ["getObjPositionInParent"]
        )

    @patch("plone.typesense.patches.TypesenseManager")
    @patch("Products.CMFCore.indexing.getQueue")
    def test_skips_missing_objects(self, mock_get_queue, mock_manager_cls):
        from plone.typesense.patches import moveObjectsByDelta

        mock_manager = MagicMock()
        mock_manager.active = True
        mock_manager_cls.return_value = mock_manager

        # item2 doesn't exist in container
        objects = {"item1": MagicMock()}
        container = self._make_container(objects)

        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        moveObjectsByDelta(container, ["item1", "item2"], 1)

        # Only item1 should be reindexed
        self.assertEqual(mock_queue.reindex.call_count, 1)

    @patch("plone.typesense.patches.TypesenseManager")
    @patch("Products.CMFCore.indexing.getQueue")
    def test_passes_subset_ids_and_suppress_events(
        self, mock_get_queue, mock_manager_cls
    ):
        from plone.typesense.patches import moveObjectsByDelta

        mock_manager = MagicMock()
        mock_manager.active = False
        mock_manager_cls.return_value = mock_manager

        container = self._make_container()
        moveObjectsByDelta(
            container, ["item1"], 2,
            subset_ids=["item1", "item2"],
            suppress_events=True,
        )

        container._old_moveObjectsByDelta.assert_called_once_with(
            ["item1"], 2,
            subset_ids=["item1", "item2"],
            suppress_events=True,
        )

    @patch("plone.typesense.patches.TypesenseManager")
    def test_returns_original_result_on_error(self, mock_manager_cls):
        from plone.typesense.patches import moveObjectsByDelta

        mock_manager = MagicMock()
        mock_manager.active = True
        mock_manager_cls.return_value = mock_manager

        container = self._make_container()
        container._old_moveObjectsByDelta.return_value = 42

        # getQueue import will fail since we don't patch it
        # but the function should still return the original result
        with patch(
            "Products.CMFCore.indexing.getQueue",
            side_effect=Exception("queue error"),
        ):
            result = moveObjectsByDelta(container, ["item1"], 1)

        self.assertEqual(result, 42)
