import transaction
from Products.CMFCore.interfaces import ICatalogAware
from Products.Five.browser import BrowserView
from zope.component import getUtility
from zope.interface import Interface
from zope.interface import implementer

from plone import api
from plone.typesense import _
from plone.typesense import log
from plone.typesense.global_utilities.typesense import ITypesenseConnector


class ITypesenseConvert(Interface):
    """Marker Interface for ITypesenseConvert"""


@implementer(ITypesenseConvert)
class TypesenseConvert(BrowserView):
    """Convert/initialize Typesense collection from existing Plone catalog.

    Creates or recreates the Typesense collection using the configured schema,
    then triggers a full reindex of all catalog content.
    """

    def __call__(self):
        authenticator = self.context.restrictedTraverse("@@authenticator")
        if not authenticator.verify():
            raise Unauthorized("Invalid CSRF token")

        self.convert_results = self._convert()
        return self.index()

    def _convert(self):
        """Initialize collection and reindex all content."""
        ts_connector = getUtility(ITypesenseConnector)

        # Initialize (or reinitialize) the collection with the configured schema
        log.info("Convert: initializing Typesense collection")
        ts_connector.clear()

        # Now reindex all content
        indexed = self._reindex_all(ts_connector)

        results = {
            "collection_name": ts_connector.collection_base_name,
            "indexed": indexed,
        }
        log.info(
            f"Convert complete: collection '{ts_connector.collection_base_name}' "
            f"initialized with {indexed} documents"
        )
        return results

    def _reindex_all(self, ts_connector):
        """Reindex all catalog content into Typesense."""
        from plone.typesense.queueprocessor import IndexProcessor

        processor = IndexProcessor()
        catalog = api.portal.get_tool("portal_catalog")
        # Use _old_searchResults to get all content, bypassing Typesense
        # routing. Must pass a query parameter (path) because ZCatalog
        # returns empty results when called with no arguments.
        portal_path = "/".join(api.portal.get().getPhysicalPath())
        search = getattr(
            catalog, "_old_searchResults",
            catalog.searchResults,
        )
        brains = search(path=portal_path)

        bulk_size = 50
        try:
            bulk_size = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.bulk_size"
            )
        except (KeyError, api.exc.InvalidParameterError):
            pass

        indexed = 0
        batch = []

        for brain in brains:
            uid = brain.UID
            if not uid:
                continue
            try:
                data = processor.get_data(uid)
                if data:
                    data["id"] = uid
                    batch.append(data)
            except Exception as exc:
                log.warning(
                    f"Convert: could not get data for UID {uid}: {exc}"
                )
                continue

            if len(batch) >= bulk_size:
                try:
                    ts_connector.index(batch)
                    indexed += len(batch)
                except Exception as exc:
                    log.error(f"Convert: error indexing batch: {exc}")
                batch = []
                transaction.savepoint(optimistic=True)

        if batch:
            try:
                ts_connector.index(batch)
                indexed += len(batch)
            except Exception as exc:
                log.error(f"Convert: error indexing final batch: {exc}")

        return indexed
