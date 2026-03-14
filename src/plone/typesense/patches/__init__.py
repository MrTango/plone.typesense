"""Monkey patches for Plone CatalogTool to route queries and indexing to Typesense.

These patches intercept catalog search and indexing methods and route them to
Typesense when it's active, falling back to the original Plone catalog when inactive.
"""
from zope.component import queryUtility

from plone.typesense import log
from plone.typesense.interfaces import ITypesenseSearchIndexQueueProcessor
from plone.typesense.manager import TypesenseManager


def safeSearchResults(self, REQUEST=None, **kw):
    """Patched searchResults that routes to Typesense when active.

    This replaces CatalogTool.searchResults() and CatalogTool.__call__().
    When Typesense is active, queries are routed to TypesenseManager.
    When inactive, uses the original Plone catalog implementation.

    @param self: CatalogTool instance
    @param REQUEST: Optional request object or query dict
    @param kw: Query parameters
    @return: Search results (LazyMap of brains)
    """
    manager = TypesenseManager()
    active = manager.active

    log.debug(f"safeSearchResults called, active={active}")

    if active:
        # Route to Typesense
        return manager.search_results(REQUEST, check_perms=True, **kw)
    else:
        # Fall back to original Plone catalog
        return self._old_searchResults(REQUEST, **kw)


def unrestrictedSearchResults(self, REQUEST=None, **kw):
    """Patched unrestrictedSearchResults that routes to Typesense when active.

    This replaces CatalogTool.unrestrictedSearchResults().
    Similar to safeSearchResults but without permission checks.

    @param self: CatalogTool instance
    @param REQUEST: Optional request object or query dict
    @param kw: Query parameters
    @return: Search results (LazyMap of brains)
    """
    manager = TypesenseManager()
    active = manager.active

    log.debug(f"unrestrictedSearchResults called, active={active}")

    if active:
        # Route to Typesense (no permission checks)
        return manager.search_results(REQUEST, check_perms=False, **kw)
    else:
        # Fall back to original Plone catalog
        return self._old_unrestrictedSearchResults(REQUEST, **kw)


def uncatalog_object(self, uid, *args, **kwargs):
    """Patched uncatalog_object that queues a Typesense delete.

    Extracts the UUID from the catalog brain BEFORE calling the original
    method, since the object/brain may be gone afterwards.

    @param self: CatalogTool instance
    @param uid: Object path (not UUID)
    """
    uuid_to_delete = None
    processor = None
    try:
        processor = queryUtility(
            ITypesenseSearchIndexQueueProcessor, name="typesense"
        )
        if processor and processor.active:
            rid = self._catalog.uids.get(uid)
            if rid is not None:
                metadata = self._catalog.getMetadataForRID(rid)
                uuid_to_delete = metadata.get("UID")
    except Exception:
        log.debug("Could not extract UID for Typesense delete: %s", uid)

    # Call original uncatalog_object
    result = self._old_uncatalog_object(uid, *args, **kwargs)

    # Queue Typesense delete
    if uuid_to_delete and processor:
        try:
            actions = processor.actions
            if uuid_to_delete in actions.index:
                actions.index.pop(uuid_to_delete)
            if uuid_to_delete in actions.reindex:
                actions.reindex.pop(uuid_to_delete)
            actions.unindex[uuid_to_delete] = {}
            log.debug(f"Queued Typesense delete for {uid} (UUID={uuid_to_delete})")
        except Exception:
            log.warning("Could not queue Typesense delete for %s", uid)

    return result


def manage_catalogRebuild(self, *args, **kwargs):
    """Patched manage_catalogRebuild: clear Typesense and set IReindexActive.

    Clears the Typesense collection before the catalog rebuild starts,
    and sets the IReindexActive marker on the request so the IndexProcessor
    knows to index all attributes for every object.
    """
    from zope.globalrequest import getRequest
    from zope.interface import alsoProvides, noLongerProvides
    from plone.typesense.interfaces import IReindexActive

    processor = queryUtility(
        ITypesenseSearchIndexQueueProcessor, name="typesense"
    )
    request = getRequest()

    if processor and processor.active:
        try:
            processor.ts_connector.clear()
            log.info("Cleared Typesense collection for catalog rebuild")
        except Exception:
            log.error(
                "Failed to clear Typesense collection during rebuild",
                exc_info=True,
            )
        if request is not None:
            alsoProvides(request, IReindexActive)

    try:
        result = self._old_manage_catalogRebuild(*args, **kwargs)
    finally:
        if request is not None and IReindexActive.providedBy(request):
            noLongerProvides(request, IReindexActive)

    return result


def manage_catalogClear(self, *args, **kwargs):
    """Patched manage_catalogClear: clear Typesense collection.

    Clears the Typesense collection before the standard catalog clear.
    """
    processor = queryUtility(
        ITypesenseSearchIndexQueueProcessor, name="typesense"
    )

    if processor and processor.active:
        try:
            processor.ts_connector.clear()
            log.info("Cleared Typesense collection for catalog clear")
        except Exception:
            log.error(
                "Failed to clear Typesense collection during catalog clear",
                exc_info=True,
            )

    return self._old_manage_catalogClear(*args, **kwargs)
