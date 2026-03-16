# -*- coding: utf-8 -*-
import transaction
from Products.Five.browser import BrowserView
from zope.component import getUtility
from zope.interface import Interface
from zope.interface import implementer

from plone import api
from plone.typesense import _
from plone.typesense import log
from plone.typesense.global_utilities.typesense import ITypesenseConnector


class ITypesenseSync(Interface):
    """Marker Interface for ITypesenseSync"""


@implementer(ITypesenseSync)
class TypesenseSync(BrowserView):
    """Synchronize Plone catalog with Typesense collection.

    Performs bidirectional UID comparison:
    - Indexes objects present in Plone catalog but missing from Typesense
    - Deletes orphan documents in Typesense that are no longer in catalog
    """

    def __call__(self):
        authenticator = self.context.restrictedTraverse("@@authenticator")
        if not authenticator.verify():
            raise Unauthorized("Invalid CSRF token")

        self.sync_results = self._synchronize()
        return self.index()

    def _get_catalog_uids(self):
        """Get all UIDs from the Plone catalog.

        Uses the UID index directly to get the true set of cataloged UIDs,
        bypassing both Typesense routing and ZCatalog's empty-query behavior.
        """
        catalog = api.portal.get_tool("portal_catalog")
        uid_index = catalog._catalog.indexes.get("UID")
        if uid_index is None:
            return set()
        return set(uid_index.uniqueValues())

    def _get_typesense_uids(self, ts_connector):
        """Get all document IDs from the Typesense collection.

        Uses search with pagination to retrieve all document IDs.
        """
        ts_client = ts_connector.get_client()
        collection_name = ts_connector.collection_base_name
        uids = set()
        page = 1
        per_page = 250

        try:
            while True:
                results = ts_client.collections[collection_name].documents.search(
                    {
                        "q": "*",
                        "per_page": per_page,
                        "page": page,
                        "include_fields": "id",
                    }
                )
                hits = results.get("hits", [])
                if not hits:
                    break
                for hit in hits:
                    doc_id = hit.get("document", {}).get("id")
                    if doc_id:
                        uids.add(doc_id)
                found = results.get("found", 0)
                if page * per_page >= found:
                    break
                page += 1
        except Exception as exc:
            log.error(f"Error retrieving Typesense documents: {exc}")

        return uids

    def _index_missing_objects(self, missing_uids, ts_connector):
        """Index objects that are in catalog but not in Typesense."""
        from plone.typesense.queueprocessor import IndexProcessor

        processor = IndexProcessor()
        catalog = api.portal.get_tool("portal_catalog")
        bulk_size = 50
        try:
            bulk_size = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.bulk_size"
            )
        except Exception:
            pass

        indexed = 0
        batch = []
        for uid in missing_uids:
            search = getattr(
                catalog, "_old_searchResults",
                catalog.searchResults,
            )
            brains = search(UID=uid)
            if not brains:
                continue
            brain = brains[0]
            try:
                obj = brain.getObject()
            except Exception:
                log.warning(f"Could not resolve object for UID: {uid}")
                continue

            data = processor.get_data(uid)
            if data:
                data["id"] = uid
                batch.append(data)

            if len(batch) >= bulk_size:
                ts_connector.index(batch)
                indexed += len(batch)
                batch = []
                transaction.savepoint(optimistic=True)

        if batch:
            ts_connector.index(batch)
            indexed += len(batch)

        return indexed

    def _delete_orphan_documents(self, orphan_uids, ts_connector):
        """Delete documents from Typesense that are no longer in catalog."""
        ts_client = ts_connector.get_client()
        collection_name = ts_connector.collection_base_name
        deleted = 0

        for uid in orphan_uids:
            try:
                ts_client.collections[collection_name].documents[uid].delete()
                deleted += 1
            except Exception as exc:
                log.warning(
                    f"Could not delete orphan document {uid} from Typesense: {exc}"
                )

        return deleted

    def _synchronize(self):
        """Perform the synchronization."""
        ts_connector = getUtility(ITypesenseConnector)

        catalog_uids = self._get_catalog_uids()
        typesense_uids = self._get_typesense_uids(ts_connector)

        missing_uids = catalog_uids - typesense_uids
        orphan_uids = typesense_uids - catalog_uids

        indexed = 0
        deleted = 0

        if missing_uids:
            log.info(
                f"Synchronize: {len(missing_uids)} objects missing from Typesense"
            )
            indexed = self._index_missing_objects(missing_uids, ts_connector)

        if orphan_uids:
            log.info(
                f"Synchronize: {len(orphan_uids)} orphan documents in Typesense"
            )
            deleted = self._delete_orphan_documents(orphan_uids, ts_connector)

        results = {
            "catalog_count": len(catalog_uids),
            "typesense_count": len(typesense_uids),
            "missing": len(missing_uids),
            "orphans": len(orphan_uids),
            "indexed": indexed,
            "deleted": deleted,
        }

        log.info(
            f"Synchronization complete: indexed {indexed}, deleted {deleted}"
        )
        return results
