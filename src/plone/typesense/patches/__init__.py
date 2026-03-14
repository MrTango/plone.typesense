"""Monkey patches for Plone CatalogTool to route queries to Typesense.

These patches intercept catalog search methods and route them to Typesense
when it's active, falling back to the original Plone catalog when inactive.
Also patches moveObjectsByDelta to reindex positions in Typesense when
content is reordered.
"""
from plone.typesense import log
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


def moveObjectsByDelta(self, ids, delta, subset_ids=None,
                       suppress_events=False):
    """Patched moveObjectsByDelta to reindex positions in Typesense.

    When content is reordered in a folder, the getObjPositionInParent
    index needs to be updated in Typesense for all affected objects.
    This patch calls the original method first, then queues reindex
    operations for the moved objects.

    @param self: OrderedContainer/Folder instance
    @param ids: List of object ids to move
    @param delta: Number of positions to move (positive=down, negative=up)
    @param subset_ids: Optional subset of ids to consider for ordering
    @param suppress_events: If True, don't fire events
    @return: Result from original moveObjectsByDelta
    """
    # Call original method first
    result = self._old_moveObjectsByDelta(
        ids, delta, subset_ids=subset_ids,
        suppress_events=suppress_events
    )

    # Queue reindex for affected objects in Typesense
    try:
        manager = TypesenseManager()
        if not manager.active:
            return result

        from Products.CMFCore.indexing import getQueue

        queue = getQueue()

        if isinstance(ids, str):
            ids = [ids]

        for obj_id in ids:
            obj = self.get(obj_id)
            if obj is not None:
                log.debug(
                    f"moveObjectsByDelta: queueing reindex for "
                    f"{obj_id} (getObjPositionInParent)"
                )
                queue.reindex(obj, ["getObjPositionInParent"])

    except Exception as exc:
        log.warning(
            f"Failed to queue Typesense reindex after moveObjectsByDelta: "
            f"{exc}"
        )

    return result
