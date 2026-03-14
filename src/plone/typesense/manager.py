from Products.CMFCore.indexing import processQueue
from zope.interface import implementer
from ZTUtils.Lazy import LazyMap
from plone.typesense import interfaces, utils
from plone.typesense.result import BrainFactory, TypesenseResult
from DateTime import DateTime
from Products.CMFPlone.CatalogTool import CatalogTool
from plone import api
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.permissions import AccessInactivePortalContent
from plone.typesense import log
from zope.component import getUtility
from plone.typesense.global_utilities.typesense import ITypesenseConnector


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

    @property
    def active(self):
        """Check if Typesense is active (enabled and configured)."""
        return self.enabled

    @property
    def raise_search_exception(self):
        """Whether to raise exceptions on search errors or fallback to catalog."""
        # Default to False - fallback to catalog on errors
        return False

    @property
    def collection_name(self):
        """Get the Typesense collection name."""
        connector = getUtility(ITypesenseConnector)
        return connector.collection_base_name

    def get_record_by_path(self, path: str) -> dict:
        """Get a single record by path from Typesense."""
        params = {
            'q': '*',
            'filter_by': f'path:={path}',
            'per_page': 1
        }
        try:
            connector = getUtility(ITypesenseConnector)
            client = connector.get_client()
            results = client.collections[self.collection_name].documents.search(params)
            hits = results.get("hits", [])
            return hits[0]["document"] if hits else {}
        except Exception as e:
            log.error(f"Error fetching record by path {path}: {e}", exc_info=True)
            return {}

    @property
    def bulk_size(self) -> int:
        """Bulk size of TypeSense calls."""
        try:
            from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import ITypesenseControlpanel
            value = api.portal.get_registry_record(
                "bulk_size", ITypesenseControlpanel, 50
            )
        except Exception:
            # Default to 50 if registry not available (e.g., during tests)
            value = 50
        return value

    @property
    def highlight(self):
        """Is search highlighting enabled in the control panel."""
        try:
            from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import ITypesenseControlpanel
            value = api.portal.get_registry_record(
                "highlight", ITypesenseControlpanel, False
            )
        except Exception:
            value = False
        return value

    @property
    def highlight_threshold(self):
        """Threshold for highlight fragments."""
        try:
            from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import ITypesenseControlpanel
            return api.portal.get_registry_record(
                "highlight_threshold", ITypesenseControlpanel, 200
            )
        except Exception:
            return 200

    def _search(self, query_params, sort=None, start=0, size=None):
        """Execute Typesense search with given parameters.

        @param query_params: Typesense search parameters dict with q, query_by, filter_by, etc.
        @param sort: List of sort tuples/dicts from normalize()
        @param start: Starting position for results
        @param size: Number of results to return
        @return: dict with 'hits' (list of hits) and 'found' (total count)
        """
        connector = getUtility(ITypesenseConnector)
        client = connector.get_client()

        # Convert pagination
        per_page = size if size else self.bulk_size
        page = (start // per_page) + 1 if start > 0 else 1

        params = query_params.copy()
        params['per_page'] = per_page
        params['page'] = page

        # Convert sort to Typesense format
        if sort:
            sort_parts = []
            for sort_item in sort:
                if isinstance(sort_item, dict):
                    for field, opts in sort_item.items():
                        if isinstance(opts, dict):
                            order = opts.get('order', 'asc')
                            sort_parts.append(f"{field}:{order}")
                elif isinstance(sort_item, str) and sort_item != '_score':
                    sort_parts.append(f"{sort_item}:asc")
            if sort_parts:
                params['sort_by'] = ','.join(sort_parts)

        log.debug(f"Typesense search params: {params}")

        # Execute search
        results = client.collections[self.collection_name].documents.search(params)

        return {
            'hits': results.get('hits', []),
            'found': results.get('found', 0)
        }

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

    def search_results(self, request=None, check_perms=False, **kw):
        """Execute search via Typesense.

        This method is ONLY called when Typesense is active (via monkey patches).
        The patches in .patches module handle routing - this method just executes the search.

        @param request: Optional request object or query dict
        @param check_perms: Whether to apply permission filtering
        @param kw: Query parameters
        @return: Search results (LazyMap of brains)
        """
        # Make sure any pending index tasks have been processed
        processQueue()

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
        log.debug(f"Typesense search with query: {orig_query}")

        try:
            result = self.search(query)
            return result
        except Exception:
            if self.raise_search_exception is True:
                raise
            log.error(f"Error running Typesense query: {orig_query}", exc_info=True)
            # Fall back to original catalog search on error
            fallback_method = (
                self.catalog._old_searchResults if check_perms
                else self.catalog._old_unrestrictedSearchResults
            )
            return fallback_method(request, **kw)
