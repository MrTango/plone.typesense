"""Monkey patches for Plone CatalogTool to route queries to Typesense.

These patches intercept catalog search methods and route them to Typesense
when it's active, falling back to the original Plone catalog when inactive.
"""
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
    print(f"\n{'='*80}", flush=True)
    print(f"[PATCH] safeSearchResults called", flush=True)
    print(f"[PATCH] REQUEST type: {type(REQUEST)}", flush=True)
    print(f"[PATCH] REQUEST: {REQUEST}", flush=True)
    print(f"[PATCH] kw: {kw}", flush=True)

    manager = TypesenseManager()
    active = manager.active

    print(f"[PATCH] TypesenseManager.enabled = {manager.enabled}", flush=True)
    print(f"[PATCH] TypesenseManager.active = {active}", flush=True)
    print(f"{'='*80}\n", flush=True)

    if active:
        # Route to Typesense
        print("[PATCH] Routing to Typesense...", flush=True)
        return manager.search_results(REQUEST, check_perms=True, **kw)
    else:
        # Fall back to original Plone catalog
        print("[PATCH] Falling back to original catalog...", flush=True)
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
    print(f"\n{'='*80}", flush=True)
    print(f"[PATCH] unrestrictedSearchResults called", flush=True)
    print(f"[PATCH] REQUEST type: {type(REQUEST)}", flush=True)
    print(f"[PATCH] REQUEST: {REQUEST}", flush=True)
    print(f"[PATCH] kw: {kw}", flush=True)

    manager = TypesenseManager()
    active = manager.active

    print(f"[PATCH] TypesenseManager.enabled = {manager.enabled}", flush=True)
    print(f"[PATCH] TypesenseManager.active = {active}", flush=True)
    print(f"{'='*80}\n", flush=True)

    if active:
        # Route to Typesense (no permission checks)
        print("[PATCH] Routing to Typesense (unrestricted)...", flush=True)
        return manager.search_results(REQUEST, check_perms=False, **kw)
    else:
        # Fall back to original Plone catalog
        print("[PATCH] Falling back to original catalog (unrestricted)...", flush=True)
        return self._old_unrestrictedSearchResults(REQUEST, **kw)
