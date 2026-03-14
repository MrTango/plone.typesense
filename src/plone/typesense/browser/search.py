"""Custom search view to prevent Plone from mangling search terms.

Plone's default @@search view modifies query strings in ways that are
incompatible with Typesense (e.g., appending wildcards, splitting on
whitespace, lowercasing).  This view intercepts the search request and
passes the raw query text directly to the Typesense manager.
"""

from plone import api
from Products.Five.browser import BrowserView
from zope.component import queryUtility

from plone.typesense import log
from plone.typesense.interfaces import ITypesenseManager


class TypesenseSearchView(BrowserView):
    """Browser view that provides a clean search endpoint for Typesense.

    Usage:
        @@typesense-search?SearchableText=my+query&portal_type=Document

    This view:
    1. Reads search parameters from the request without Plone's
       query mangling (no wildcard injection, no term splitting).
    2. Passes them through the TypesenseManager.search() pipeline.
    3. Returns results as a standard Plone lazy catalog result set,
       compatible with existing search templates.
    """

    # Parameters that are NOT search query fields
    _meta_params = frozenset({
        "b_start", "b_size", "sort_on", "sort_order", "sort_limit",
    })

    def __call__(self):
        """Execute search and return results via the template."""
        results = self.results()
        # If a template is registered, render it; otherwise return
        # the results object for use by AJAX / REST callers.
        if hasattr(self, "index"):
            return self.index()
        return results

    def results(self):
        """Run the search and return a lazy result set."""
        query = self._build_query()
        if not query:
            return []

        manager = queryUtility(ITypesenseManager)
        if manager is None or not getattr(manager, "enabled", False):
            # Fallback to standard catalog search
            catalog = api.portal.get_tool("portal_catalog")
            return catalog.searchResults(**query)

        try:
            return manager.search(query)
        except Exception:
            log.error("Typesense search failed, falling back to catalog", exc_info=True)
            catalog = api.portal.get_tool("portal_catalog")
            return catalog.searchResults(**query)

    def _build_query(self):
        """Build a clean query dict from the request.

        Preserves the raw SearchableText without mangling.
        """
        form = self.request.form
        query = {}

        for key, value in form.items():
            if not value:
                continue
            # Skip internal Zope/Plone parameters
            if key.startswith("_") or key.startswith("form."):
                continue
            query[key] = value

        return query

    @property
    def search_term(self):
        """The raw search term for display in templates."""
        return self.request.form.get("SearchableText", "")

    @property
    def batch_size(self):
        """Number of results per page."""
        try:
            return int(self.request.form.get("b_size", 20))
        except (TypeError, ValueError):
            return 20

    @property
    def batch_start(self):
        """Starting index for pagination."""
        try:
            return int(self.request.form.get("b_start", 0))
        except (TypeError, ValueError):
            return 0
