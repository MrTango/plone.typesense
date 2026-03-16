"""Reindex view: clears and rebuilds the Typesense collection from catalog."""
from Products.CMFCore.interfaces import ICatalogAware
from Products.Five.browser import BrowserView
from zope.component import getUtility
from zope.interface import Interface, alsoProvides, implementer, noLongerProvides

from plone import api
from plone.typesense import log
from plone.typesense.interfaces import (
    IReindexActive,
    ITypesenseSearchIndexQueueProcessor,
)


class ITypesenseReindexCollection(Interface):
    """Marker Interface for ITypesenseReindexCollection"""


@implementer(ITypesenseReindexCollection)
class TypesenseReindexCollection(BrowserView):

    def __call__(self):
        # Only process on POST (form submission with CSRF token)
        if self.request.method != "POST":
            return self.index()

        # CSRF protection
        from plone.protect import CheckAuthenticator
        CheckAuthenticator(self.request)

        processor = getUtility(
            ITypesenseSearchIndexQueueProcessor, name="typesense"
        )

        if not processor.active:
            api.portal.show_message(
                "Typesense is not active.", self.request, type="warning"
            )
            return self.index()

        # Clear Typesense collection before reindex
        try:
            processor.ts_connector.clear()
            log.info("Cleared Typesense collection for full reindex")
        except Exception:
            log.error("Failed to clear Typesense before reindex", exc_info=True)

        alsoProvides(self.request, IReindexActive)

        count = 0
        errors = 0
        batch_size = 100

        try:
            catalog = api.portal.get_tool("portal_catalog")
            # Use _old_searchResults to bypass Typesense routing.
            # Must pass a query (path) because ZCatalog returns empty
            # with no arguments.
            portal_path = "/".join(api.portal.get().getPhysicalPath())
            search = getattr(
                catalog, "_old_searchResults",
                catalog.searchResults,
            )
            brains = search(path=portal_path)

            for brain in brains:
                try:
                    obj = brain.getObject()
                except Exception:
                    log.warning(f"Could not resolve brain: {brain.getPath()}")
                    errors += 1
                    continue

                if not ICatalogAware.providedBy(obj):
                    continue

                processor.index(obj)
                count += 1

                if count % batch_size == 0:
                    processor.commit()
                    log.info(f"Reindex progress: {count} objects processed")

            # Final commit for remaining objects
            processor.commit()

        finally:
            noLongerProvides(self.request, IReindexActive)

        msg = f"Reindexed {count} objects into Typesense."
        if errors:
            msg += f" {errors} objects could not be resolved."
        log.info(msg)
        api.portal.show_message(msg, self.request, type="info")
        return self.index()
