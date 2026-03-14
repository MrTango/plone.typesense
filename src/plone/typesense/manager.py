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
