from Products.CMFCore.indexing import processQueue
from zope.interface import implementer
from ZTUtils.Lazy import LazyMap
from plone.typesense import interfaces, utils
from plone.typesense.result import BrainFactory, FacetResult, TypesenseResult
from DateTime import DateTime
from Products.CMFPlone.CatalogTool import CatalogTool
from plone import api
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.permissions import AccessInactivePortalContent
from plone.typesense import log


@implementer(interfaces.ITypesenseManager)
class TypesenseManager:
    """
    """

    _catalog: CatalogTool = None

    @property
    def catalog(self):
        return api.portal.get_tool("portal_catalog")

    @property
    def enabled(self):
        try:
            return api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.enabled"
            )
        except api.exc.InvalidParameterError:
            value = False
        return value

    # XXX
    def get_record_by_path(self, path: str) -> dict:
        body = {"query": {"match": {"path.path": path}}}
        results = self.connection.search(index=self.index_name, body=body)
        hits = results.get("hits", {}).get("hits", [])
        record = hits[0]["_source"] if hits else {}
        return record

    @property
    def bulk_size(self) -> int:
        """Bulk size of TypeSense calls."""
        try:
            value = api.portal.get_registry_record(
                "bulk_size", interfaces.ITypesenseSettings, 50
            )
        except KeyError:
            value = 50
        return value

    @property
    def highlight(self):
        """Is search highlighting enabled in the control panel."""
        try:
            value = api.portal.get_registry_record(
                "highlight", interfaces.ITypesenseSettings, False
            )
        except KeyError:
            value = False
        return value

    @property
    def highlight_start_tag(self):
        """Opening tag for search result highlighting."""
        try:
            value = api.portal.get_registry_record(
                "highlight_start_tag", interfaces.ITypesenseSettings, "<mark>"
            )
        except KeyError:
            value = "<mark>"
        return value

    @property
    def highlight_end_tag(self):
        """Closing tag for search result highlighting."""
        try:
            value = api.portal.get_registry_record(
                "highlight_end_tag", interfaces.ITypesenseSettings, "</mark>"
            )
        except KeyError:
            value = "</mark>"
        return value

    @property
    def highlight_fields(self):
        """Fields to highlight in search results."""
        try:
            value = api.portal.get_registry_record(
                "highlight_fields", interfaces.ITypesenseSettings, None
            )
        except KeyError:
            value = None
        return value or ["Title", "Description", "SearchableText"]

    def _get_highlight_params(self):
        """Build Typesense highlight search parameters from control panel settings.

        Returns a dict of highlight-related search params, or empty dict
        if highlighting is disabled.
        """
        if not self.highlight:
            return {}
        params = {
            "highlight_fields": ",".join(self.highlight_fields),
            "highlight_start_tag": self.highlight_start_tag,
            "highlight_end_tag": self.highlight_end_tag,
        }
        return params

    def _search(self, query_params, sort=None, start=0, size=None, **extra_params):
        """Execute Typesense search with given parameters.

        @param query_params: Typesense search parameters dict with q, query_by, filter_by, etc.
        @param sort: Sort string for Typesense
        @param start: Starting position for results
        @param size: Number of results to return
        @return: dict with 'hits' (list of hits) and 'found' (total count)
        """
        connector = getUtility(ITypesenseConnector)
        client = connector.get_client()

        per_page = size if size else self.bulk_size
        page = (start // per_page) + 1 if start > 0 else 1

        params = query_params.copy()
        params.update(extra_params)
        params['per_page'] = per_page
        params['page'] = page

        if sort:
            params['sort_by'] = sort

        # Add highlight params
        params.update(self._get_highlight_params())

        log.debug(f"Typesense search params: {params}")

        results = client.collections[self.collection_name].documents.search(params)

        return {
            'hits': results.get('hits', []),
            'found': results.get('found', 0),
            'facet_counts': results.get('facet_counts', []),
        }

    def generate_scoped_search_key(self, user=None):
        """Generate a scoped search API key for the given user.

        The key embeds the user's allowedRolesAndUsers as a filter,
        enabling secure client-side search.

        :param user: The user to generate the key for (defaults to current user)
        :returns: scoped API key string, or None if not configured
        """
        from plone.typesense.scoped_search import generate_scoped_search_key

        try:
            search_api_key = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.search_api_key"
            )
        except api.exc.InvalidParameterError:
            search_api_key = None

        if not search_api_key:
            log.warning("No search API key configured for scoped key generation")
            return None

        try:
            collection_name = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.collection"
            )
        except api.exc.InvalidParameterError:
            log.warning("No collection name configured")
            return None

        return generate_scoped_search_key(search_api_key, collection_name, user)

    def search(self, query: dict, factory=None, **query_params) -> LazyMap:
        """
        @param query: The Plone query
        @param factory: The factory that maps each typesense search result.
            By default, get the plone catalog brain.
        @param query_params: Parameters to pass to the search method
            'stored_fields': the list of fields to get from stored source
        """
        factory = BrainFactory(self)
        result = TypesenseResult(self, query, **query_params)
        return LazyMap(factory, result, result.count)

    def faceted_search(self, query, facet_fields, max_facet_values=10,
                       **query_params):
        """Execute a search with faceting and return results + facet counts.

        Parameters
        ----------
        query : dict
            The Plone-style query parameters.
        facet_fields : list[str]
            List of field names to facet on. These fields must have
            ``facet: true`` in the Typesense schema.
        max_facet_values : int
            Maximum number of facet values to return per field.
        **query_params :
            Additional parameters passed to the search method.

        Returns
        -------
        FacetResult
            Object with ``.results`` (LazyMap) and ``.facet_counts`` (dict)
            attributes.
        """
        query_params["facet_by"] = ",".join(facet_fields)
        query_params["max_facet_values"] = max_facet_values

        factory = BrainFactory(self)
        result = TypesenseResult(self, query, **query_params)
        lazy_results = LazyMap(factory, result, result.count)

        return FacetResult(
            results=lazy_results,
            facet_counts=result.facet_counts,
            count=result.count,
        )

    def search_results(self, request=None, check_perms=False, **kw):
        # Make sure any pending index tasks have been processed
        processQueue()
        if not (self.active and utils.get_ts_only_indexes().intersection(kw.keys())):
            method = (
                self.catalog._old_searchResults
                if check_perms
                else self.catalog._old_unrestrictedSearchResults
            )
            return method(request, **kw)

        query = request.copy() if isinstance(request, dict) else {}
        query.update(kw)

        if check_perms:
            show_inactive = query.get("show_inactive", False)
            if isinstance(request, dict) and not show_inactive:
                show_inactive = "show_inactive" in request

            user = api.user.get_current()
            query["allowedRolesAndUsers"] = self.catalog._listAllowedRolesAndUsers(user)

            if not show_inactive and not _checkPermission(
                AccessInactivePortalContent, self.catalog
            ):
                query["effectiveRange"] = DateTime()
        orig_query = query.copy()
        log.debug(f"Running query: {orig_query}")
        try:
            return self.search(query)
        except Exception:  # NOQA W0703
            if self.raise_search_exception is True:
                raise
            log.error(f"Error running Query: {orig_query}", exc_info=True)
            return self.catalog._old_searchResults(request, **kw)
