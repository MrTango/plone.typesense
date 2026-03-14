from plone import api
from plone.restapi.services import Service
from plone.typesense import log
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from Products.CMFCore.interfaces import ICatalogAware
from zope.component import getUtility


class TypesenseInfo(Service):
    """GET @typesense-info — connection status, collection info, doc counts."""

    def reply(self):
        ts_connector = getUtility(ITypesenseConnector)

        result = {
            "@id": f"{self.context.absolute_url()}/@typesense-info",
            "enabled": ts_connector.enabled,
            "connection": None,
            "collection": None,
        }

        if not ts_connector.enabled:
            result["connection"] = {"status": "disabled"}
            return result

        # Test connection
        try:
            ts_client = ts_connector.get_client()
            healthy = ts_client.operations.is_healthy()
            result["connection"] = {
                "status": "ok" if healthy else "unhealthy",
                "host": ts_connector.get_host,
                "port": ts_connector.get_port,
                "protocol": ts_connector.get_protocol,
            }
        except Exception as e:
            result["connection"] = {
                "status": "error",
                "message": str(e),
            }
            return result

        # Collection info
        collection_name = ts_connector.collection_base_name
        try:
            collection_info = ts_client.collections[collection_name].retrieve()
            result["collection"] = {
                "name": collection_name,
                "num_documents": collection_info.get("num_documents", 0),
                "fields": collection_info.get("fields", []),
                "default_sorting_field": collection_info.get(
                    "default_sorting_field", ""
                ),
            }
            # Try to get the aliased collection name
            try:
                aliased_name = ts_connector._get_current_aliased_collection_name()
                if aliased_name:
                    result["collection"]["aliased_name"] = aliased_name
            except Exception:
                pass
        except Exception as e:
            result["collection"] = {
                "name": collection_name,
                "status": "not_found",
                "message": str(e),
            }

        return result


class TypesenseConvert(Service):
    """POST @typesense-convert — clear and recreate collection, then reindex."""

    def reply(self):
        ts_connector = getUtility(ITypesenseConnector)

        if not ts_connector.enabled:
            self.request.response.setStatus(400)
            return {
                "error": {
                    "type": "BadRequest",
                    "message": "Typesense integration is not enabled.",
                }
            }

        try:
            # Clear and recreate the collection
            ts_connector.clear()
            log.info("Collection cleared and recreated for conversion.")

            # Reindex all content
            indexed_count = self._reindex_all(ts_connector)

            return {
                "@id": f"{self.context.absolute_url()}/@typesense-convert",
                "status": "ok",
                "message": f"Collection converted. {indexed_count} objects indexed.",
                "indexed_count": indexed_count,
            }
        except Exception as e:
            log.exception("Error during typesense convert")
            self.request.response.setStatus(500)
            return {
                "error": {
                    "type": "InternalServerError",
                    "message": str(e),
                }
            }

    def _reindex_all(self, ts_connector):
        """Reindex all catalog-aware content into Typesense."""
        portal = api.portal.get()
        objects = []
        batch_size = 100
        count = 0

        def _index_object(obj, path):
            nonlocal count
            if not ICatalogAware.providedBy(obj):
                return
            objects.append(obj)
            if len(objects) >= batch_size:
                ts_connector.index(objects)
                count += len(objects)
                objects.clear()

        portal.ZopeFindAndApply(portal, search_sub=True, apply_func=_index_object)

        # Index remaining objects
        if objects:
            ts_connector.index(objects)
            count += len(objects)

        return count


class TypesenseRebuild(Service):
    """POST @typesense-rebuild — full reindex of all content."""

    def reply(self):
        ts_connector = getUtility(ITypesenseConnector)

        if not ts_connector.enabled:
            self.request.response.setStatus(400)
            return {
                "error": {
                    "type": "BadRequest",
                    "message": "Typesense integration is not enabled.",
                }
            }

        try:
            # Reindex all content without clearing first
            portal = api.portal.get()
            objects = []
            batch_size = 100
            count = 0

            def _index_object(obj, path):
                nonlocal count
                if not ICatalogAware.providedBy(obj):
                    return
                objects.append(obj)
                if len(objects) >= batch_size:
                    ts_connector.index(objects)
                    count += len(objects)
                    objects.clear()

            portal.ZopeFindAndApply(
                portal, search_sub=True, apply_func=_index_object
            )

            # Index remaining objects
            if objects:
                ts_connector.index(objects)
                count += len(objects)

            return {
                "@id": f"{self.context.absolute_url()}/@typesense-rebuild",
                "status": "ok",
                "message": f"Rebuild complete. {count} objects indexed.",
                "indexed_count": count,
            }
        except Exception as e:
            log.exception("Error during typesense rebuild")
            self.request.response.setStatus(500)
            return {
                "error": {
                    "type": "InternalServerError",
                    "message": str(e),
                }
            }


class TypesenseSync(Service):
    """POST @typesense-sync — synchronize Plone catalog with Typesense."""

    def reply(self):
        ts_connector = getUtility(ITypesenseConnector)

        if not ts_connector.enabled:
            self.request.response.setStatus(400)
            return {
                "error": {
                    "type": "BadRequest",
                    "message": "Typesense integration is not enabled.",
                }
            }

        try:
            catalog = api.portal.get_tool("portal_catalog")
            collection_name = ts_connector.collection_base_name

            # Get all UIDs from the Plone catalog
            catalog_uids = set(
                brain.UID for brain in catalog.unrestrictedSearchResults()
                if brain.UID
            )

            # Get all document IDs from Typesense
            ts_client = ts_connector.get_client()
            typesense_ids = set()
            try:
                page = 1
                per_page = 250
                while True:
                    search_result = ts_client.collections[
                        collection_name
                    ].documents.search(
                        {
                            "q": "*",
                            "per_page": per_page,
                            "page": page,
                            "include_fields": "id",
                        }
                    )
                    hits = search_result.get("hits", [])
                    if not hits:
                        break
                    for hit in hits:
                        doc_id = hit.get("document", {}).get("id")
                        if doc_id:
                            typesense_ids.add(doc_id)
                    if len(hits) < per_page:
                        break
                    page += 1
            except Exception:
                # Collection may not exist yet
                pass

            # Find missing and orphaned documents
            missing_uids = catalog_uids - typesense_ids
            orphaned_ids = typesense_ids - catalog_uids

            indexed_count = 0
            deleted_count = 0

            # Index missing documents
            if missing_uids:
                objects = []
                for uid in missing_uids:
                    brains = catalog.unrestrictedSearchResults(UID=uid)
                    if brains:
                        obj = brains[0].getObject()
                        if ICatalogAware.providedBy(obj):
                            objects.append(obj)
                            if len(objects) >= 100:
                                ts_connector.index(objects)
                                indexed_count += len(objects)
                                objects.clear()
                if objects:
                    ts_connector.index(objects)
                    indexed_count += len(objects)

            # Delete orphaned documents
            if orphaned_ids:
                orphan_list = list(orphaned_ids)
                ts_connector.delete(orphan_list)
                deleted_count = len(orphan_list)

            return {
                "@id": f"{self.context.absolute_url()}/@typesense-sync",
                "status": "ok",
                "message": (
                    f"Sync complete. {indexed_count} documents indexed, "
                    f"{deleted_count} orphans removed."
                ),
                "catalog_count": len(catalog_uids),
                "typesense_count": len(typesense_ids),
                "indexed_count": indexed_count,
                "deleted_count": deleted_count,
            }
        except Exception as e:
            log.exception("Error during typesense sync")
            self.request.response.setStatus(500)
            return {
                "error": {
                    "type": "InternalServerError",
                    "message": str(e),
                }
            }
