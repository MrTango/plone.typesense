"""Event subscribers for syncing content lifecycle events to Typesense.

All handlers delegate to the IndexProcessor queue which handles
transaction integration and batching. No direct Typesense calls here.
"""
from zope.component import queryUtility

from plone.typesense import log
from plone.typesense.interfaces import ITypesenseSearchIndexQueueProcessor


def _get_processor():
    """Get the Typesense index processor if active."""
    processor = queryUtility(
        ITypesenseSearchIndexQueueProcessor, name="typesense"
    )
    if processor and processor.active:
        return processor
    return None


def object_added(obj, event):
    """Handle IObjectAddedEvent — index new content in Typesense."""
    # IObjectAddedEvent inherits from IObjectMovedEvent.
    # For a real add, newParent is set and oldParent is None.
    # Skip if newParent is None (shouldn't happen for add, but guard).
    if event.newParent is None:
        return
    # Skip if oldParent is also set — that's a move, handled by object_moved.
    if event.oldParent is not None:
        return
    processor = _get_processor()
    if processor is None:
        return
    log.debug(f"object_added: {obj.absolute_url()}")
    processor.index(obj)


def object_modified(obj, event):
    """Handle IObjectModifiedEvent — reindex modified content."""
    processor = _get_processor()
    if processor is None:
        return
    # Extract changed attributes from event descriptions if available
    attributes = set()
    if hasattr(event, "descriptions") and event.descriptions:
        for desc in event.descriptions:
            if hasattr(desc, "attributes"):
                attributes.update(desc.attributes)
    log.debug(f"object_modified: {obj.absolute_url()} attributes={attributes or 'all'}")
    if attributes:
        processor.reindex(obj, attributes=attributes)
    else:
        processor.reindex(obj)


def object_removed(obj, event):
    """Handle IObjectRemovedEvent — unindex deleted content."""
    # IObjectRemovedEvent inherits from IObjectMovedEvent.
    # For a real delete, oldParent is set and newParent is None.
    # Skip if newParent is set — that's a move, handled by object_moved.
    if event.newParent is not None:
        return
    processor = _get_processor()
    if processor is None:
        return
    log.debug(f"object_removed: {obj.absolute_url()}")
    processor.unindex(obj)


def object_moved(obj, event):
    """Handle IObjectMovedEvent — reindex moved/renamed content."""
    # Only handle genuine moves (both oldParent and newParent set).
    # Adds (oldParent=None) and deletes (newParent=None) are handled
    # by their specific handlers.
    if event.oldParent is None or event.newParent is None:
        return
    processor = _get_processor()
    if processor is None:
        return
    log.debug(f"object_moved: {obj.absolute_url()}")
    processor.reindex(obj)


def object_workflow_changed(obj, event):
    """Handle IActionSucceededEvent — reindex after workflow transition."""
    processor = _get_processor()
    if processor is None:
        return
    log.debug(f"object_workflow_changed: {obj.absolute_url()} action={event.action}")
    processor.reindex(obj, attributes={"review_state", "allowedRolesAndUsers"})
