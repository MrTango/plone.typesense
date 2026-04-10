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
    raise_search_exception: bool = False

    @property
    def catalog(self):
        return api.portal.get_tool("portal_catalog")

    @property
    def active(self):
        try:
            return api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.enabled"
            )
        except api.exc.InvalidParameterError:
            return False

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
                "plone.typesense.typesense_controlpanel.bulk_size"
            )
        except (KeyError, api.exc.InvalidParameterError):
            value = 50
        return value

    @property
    def highlight(self):
        """Is search highlighting enabled in the control panel."""
        try:
            value = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.highlight"
            )
        except (KeyError, api.exc.InvalidParameterError):
            value = False
        return value

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
