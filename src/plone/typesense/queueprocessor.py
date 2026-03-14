from plone.app.uuid.utils import uuidToObject
from plone.dexterity.utils import iterSchemata
from plone.indexer.interfaces import IIndexableObject, IIndexer
from plone.namedfile.interfaces import INamedBlobFileField
from zope.component import getAdapters, getUtility, queryMultiAdapter
from zope.interface import implementer
from zope.schema import getFields

from plone import api
from plone.typesense import log
from plone.typesense.blob_extraction import get_searchable_blob_text
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from plone.typesense.indexes import get_index
from plone.typesense.interfaces import (
    IAdditionalIndexDataProvider,
    IndexingActions,
    ITypesenseSearchIndexQueueProcessor,
)
from plone.typesense.utils import get_ts_only_indexes


@implementer(ITypesenseSearchIndexQueueProcessor)
class IndexProcessor:
    """ """

    _ts_connector = None
    _ts_client = None
    _all_attributes = None
    _ts_attributes = None
    _actions: IndexingActions = None
    rebuild: bool = False

    @property
    def ts_connector(self):
        """Return Typesense connector tool."""
        if not self._ts_connector:
            self._ts_connector = getUtility(ITypesenseConnector)
        return self._ts_connector

    @property
    def active(self):
        """ Typesense active?"""
        return self.ts_connector.enabled

    @property
    def ts_client(self):
        """return Typesense client"""
        if not self._ts_client:
            self._ts_client = self.ts_connector.get_client()
        return self._ts_client

    def ts_index(self, objects):
        """index objects in Typesense"""
        log.debug(f"ts_index: {len(objects)} objects")
        self.ts_connector.index(objects)

    def ts_update(self, objects):
        """update indexed objects in Typesense"""
        log.debug(f"ts_update: {len(objects)} objects")
        self.ts_connector.update(objects)

    def ts_delete(self, objects):
        """delete objects from Typesense"""
        uids = [obj["id"] for obj in objects]
        log.debug(f"ts_delete: {len(uids)} objects")
        self.ts_connector.delete(uids)

    @property
    def catalog(self):
        """Return the portal catalog."""
        return api.portal.get_tool("portal_catalog")

    @property
    def ts_attributes(self):
        """Return all attributes defined in portal catalog."""
        if not self._ts_attributes:
            self._ts_attributes = get_ts_only_indexes()
        return self._ts_attributes

    @property
    def all_attributes(self):
        """Return all attributes defined in portal catalog."""
        if not self._all_attributes:
            catalog = self.catalog
            ts_indexes = self.ts_attributes
            catalog_indexes = set(catalog.indexes())
            self._all_attributes = ts_indexes.union(catalog_indexes)
        return self._all_attributes

    def get_data(self, uuid, attributes=None):
        method = self.get_data_for_ts
        # if use_redis():
        #     method = self.get_data_for_redis
        return method(uuid, attributes=attributes)

    def get_data_for_ts(self, uuid, attributes=None):
        """Data to be sent to Typesense."""
        index_data = {}
        obj = api.portal.get() if uuid == "/" else uuidToObject(uuid, unrestricted=True)
        if not obj:
            log.warning(f"could not find obj for: {uuid}")
            return index_data
        else:
            log.debug(f"found obj: {obj.id}")
        wrapped_object = self.wrap_object(obj)
        attributes = attributes if attributes else self.all_attributes
        catalog = self.catalog
        ts_only_indexes = get_ts_only_indexes()

        for index_name in attributes:
            value = None
            index = get_index(catalog, index_name)

            # If index not in catalog but is in ts_only_indexes, create MockIndex
            if index is None and index_name in ts_only_indexes:
                from plone.typesense.indexes import TZCTextIndex
                from plone.typesense.query import MockIndex

                mock_index = MockIndex(index_name)
                index = TZCTextIndex(catalog._catalog, mock_index)

            if index is not None:
                try:
                    # value = get_index_value(wrapped_object, index)
                    value = index.get_value(wrapped_object)
                except Exception as exc:  # NOQA W0703
                    path = "/".join(obj.getPhysicalPath())
                    log.error(f"Error indexing value: {path}: {index_name}\n{exc}")
                    value = None
                if value in (None, "None"):
                    # yes, we'll index null data...
                    value = ""
                # sometimes review state is an empty list, let's fix that
                if index_name == "review_state" and isinstance(value, list):
                    value = "".join(value)
                if index_name == "total_comments" and isinstance(value, list):
                    value = len(value) and value[0] or 0
            elif index_name in self.ts_attributes:
                indexer = queryMultiAdapter(
                    (wrapped_object, catalog), IIndexer, name=index_name
                )
                if indexer:
                    value = indexer()
                else:
                    attr = getattr(obj, index_name, None)
                    value = attr() if callable(attr) else value
            # Use str, if bytes value
            value = (
                value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
            )

            # Normalize value types for Typesense
            value = self._normalize_value_for_typesense(index_name, value)

            # Skip optional fields that are None (exclude from payload)
            if value is not None:
                index_data[index_name] = value

        # Enrich SearchableText with extracted blob text
        self._enrich_with_blob_text(obj, index_data)

        additional_providers = getAdapters((obj,), IAdditionalIndexDataProvider)
        for name, adapter in additional_providers:
            try:
                index_data = adapter(catalog, index_data)
            except Exception:
                log.error(
                    f"Error in IAdditionalIndexDataProvider adapter '{name}'",
                    exc_info=True,
                )
        log.debug(f"index_data: {index_data}")
        return index_data

    def _enrich_with_blob_text(self, obj, index_data):
        """Append extracted blob text to SearchableText in index_data.

        If the content object has blob fields (PDF, DOCX, etc.), extract
        their text content and append it to SearchableText so it becomes
        searchable via Typesense.

        @param obj: The content object
        @param index_data: Dict of index data being built (modified in place)
        """
        try:
            blob_text = get_searchable_blob_text(obj)
        except Exception as exc:
            log.debug(f"Blob text extraction failed for {obj.id}: {exc}")
            blob_text = ""

        if blob_text:
            existing = index_data.get("SearchableText", "")
            if existing:
                index_data["SearchableText"] = f"{existing} {blob_text}"
            else:
                index_data["SearchableText"] = blob_text

    def _normalize_value_for_typesense(self, field_name, value):
        """Normalize field values to match Typesense schema types.

        This ensures that the data types we send match what Typesense expects
        based on the schema configuration.
        """
        # Get schema from connector
        schema = self.ts_connector.get_ts_schema
        if not schema or 'fields' not in schema:
            return value

        # Find field definition in schema
        field_def = None
        for field in schema['fields']:
            if field.get('name') == field_name:
                field_def = field
                break

        if not field_def:
            # No explicit field definition, check if auto-index will handle it
            # Auto-index fields (.*) will infer type from first value
            #
            # Known keyword fields that Typesense may have inferred as strings
            # Convert lists to comma-separated strings to match the inferred type
            if field_name in ('commentators', 'Contributors', 'Creators'):
                # These are typically keyword indexes that return lists
                # Convert to string to match Typesense's auto-inferred type
                if value in (None, '', 'None', [], (), {}):
                    return ""
                if isinstance(value, (list, tuple, set)):
                    # Join lists into comma-separated string
                    return ', '.join(str(v) for v in value if v not in (None, '', 'None'))
                return str(value) if value else ""

            # Known integer fields that Typesense may have inferred as int32/int64
            if field_name in ('total_comments', 'cmf_uid', 'getObjPositionInParent'):
                # Ensure it's an integer
                if value in (None, '', 'None', [], (), {}):
                    return 0
                if isinstance(value, (list, tuple)):
                    value = value[0] if value else 0
                try:
                    return int(value) if value else 0
                except (ValueError, TypeError):
                    log.warning(f"Could not convert {field_name}={value} to int, using 0")
                    return 0

            return value

        field_type = field_def.get('type', 'auto')
        optional = field_def.get('optional', False)

        # Handle null/empty values
        if value in (None, '', 'None', [], (), {}):
            if optional:
                # Optional fields can be omitted entirely
                return None
            # Non-optional fields need a default value
            if field_type.endswith('[]'):
                return []
            elif field_type in ('int32', 'int64', 'float'):
                return 0
            elif field_type == 'bool':
                return False
            else:
                return ""

        # Type conversions based on schema field type
        if field_type == 'string':
            # Single string - convert lists to single string
            if isinstance(value, (list, tuple, set)):
                # Join lists into a single string
                value = ', '.join(str(v) for v in value if v)
            return str(value) if value else ""

        elif field_type == 'string[]':
            # String array - ensure it's a list of strings
            if not isinstance(value, (list, tuple, set)):
                # Convert single value to list
                value = [value] if value else []
            # Convert all elements to strings
            return [str(v) for v in value if v not in (None, '', 'None')]

        elif field_type in ('int32', 'int64'):
            # Integer - convert to int
            if isinstance(value, (list, tuple)):
                value = value[0] if value else 0
            try:
                return int(value) if value else 0
            except (ValueError, TypeError):
                log.warning(f"Could not convert {field_name}={value} to int, using 0")
                return 0

        elif field_type == 'float':
            # Float - convert to float
            if isinstance(value, (list, tuple)):
                value = value[0] if value else 0.0
            try:
                return float(value) if value else 0.0
            except (ValueError, TypeError):
                log.warning(f"Could not convert {field_name}={value} to float, using 0.0")
                return 0.0

        elif field_type == 'bool':
            # Boolean - convert to bool
            if isinstance(value, (list, tuple)):
                value = value[0] if value else False
            return bool(value)

        # For auto or unknown types, return as-is
        return value

    def _clean_up(self):
        self._ts_attributes = None
        self._all_attributes = None
        self._actions = None

    @property
    def actions(self) -> IndexingActions:
        if not self._actions:
            self._actions = IndexingActions(
                index={},
                reindex={},
                unindex={},
                index_blobs={},
                uuid_path={},
            )
        return self._actions

    def wrap_object(self, obj):
        wrapped_object = None
        if not IIndexableObject.providedBy(obj):
            # This is the CMF 2.2 compatible approach, which should be used
            # going forward
            wrapper = queryMultiAdapter((obj, self.catalog), IIndexableObject)
            wrapped_object = wrapper if wrapper is not None else obj
        else:
            wrapped_object = obj
        return wrapped_object

    @property
    def rebuild(self):
        if not self.active:
            return False
        from zope.globalrequest import getRequest
        from plone.typesense.interfaces import IReindexActive
        request = getRequest()
        if request is None:
            return False
        return IReindexActive.providedBy(request)

    def _uuid_path(self, obj):
        uuid = api.content.get_uuid(obj) if obj.portal_type != "Plone Site" else "/"
        path = "/".join(obj.getPhysicalPath())
        return uuid, path

    def index(self, obj, attributes=None):
        """queue an index operation for the given object and attributes"""
        if not self.active:
            return
        actions = self.actions
        uuid, path = self._uuid_path(obj)
        actions.uuid_path[uuid] = path
        if self.rebuild:
            # During rebuild we index everything
            attributes = self.all_attributes
            is_reindex = False
        else:
            if attributes:
                # Convert to set and add ts_only_indexes
                # This ensures fields like Title are indexed even if removed from catalog
                attributes = {att for att in attributes}
                attributes = attributes.union(get_ts_only_indexes())
            else:
                attributes = set()
            is_reindex = attributes and attributes != self.all_attributes
        data = self.get_data(uuid, attributes)
        blob_data = self.get_blob_data(uuid, obj)
        if is_reindex and uuid in actions.index:
            # Reindexing something that was not processed yet
            actions.index[uuid].update(data)
            return
        elif is_reindex:
            # Simple reindexing
            actions.reindex[uuid] = data
            actions.index_blobs[uuid] = blob_data
            return
        elif uuid in actions.reindex:
            # Remove from reindex
            actions.reindex.pop(uuid)

        elif uuid in actions.unindex:
            # Remove from unindex
            actions.unindex.pop(uuid)
        actions.index[uuid] = data
        actions.index_blobs[uuid] = blob_data

    def reindex(self, obj, attributes=None, update_metadata=False):
        """queue a reindex operation for the given object and attributes"""
        if not self.active:
            return
        log.debug(f"reindex: {obj.id}: {attributes}")
        self.index(obj, attributes)

    def unindex(self, obj):
        """queue an unindex operation for the given object"""
        if not self.active:
            return
        uid = api.content.get_uuid(obj) if obj.portal_type != "Plone Site" else "/"
        if uid is None:
            return
        log.debug(f"unindex: {obj.id} (uid={uid})")
        actions = self.actions
        # Remove from index/reindex if queued
        if uid in actions.index:
            actions.index.pop(uid)
        if uid in actions.reindex:
            actions.reindex.pop(uid)
        actions.unindex[uid] = {}

    def begin(self,):
        """called before processing of the queue is started"""
        log.debug("begin()")

    def commit(self, wait=None):
        """called after processing of the queue has ended"""
        log.debug("commit()")
        self.commit_ts()

    def commit_ts(self, wait=None):
        """Transaction commit."""
        if not self.active:
            return
        actions = self.actions
        items = len(actions) if actions else 0
        if self.ts_client and items:
            ts_data = {}
            data = actions.all()
            log.debug(f"commit_ts: processing {len(data)} actions")
            for action, uuid, payload in data:
                payload = self._prepare_for_typesense(uuid, payload)
                if action not in ts_data:
                    ts_data[action] = []
                ts_data[action].append(payload)
            log.debug(f"actions: {ts_data.keys()}")
            if "index" in ts_data:
                self.ts_index(ts_data["index"])
            if "update" in ts_data:
                self.ts_update(ts_data["update"])
            if "delete" in ts_data:
                self.ts_delete(ts_data["delete"])
        self._clean_up()

    def _prepare_for_typesense(self, uuid, payload):
        """
        """
        if "id" in payload:
            plone_id = payload["id"]
            payload["plone_id"] = plone_id
        payload["id"] = uuid
        return payload

    def abort(self):
        """called if processing of the queue needs to be aborted"""
        log.debug("abort()")

    def get_blob_data(self, uuid, obj):
        """Go thru schemata and extract infos about blob fields"""
        index_data = {}
        portal_path_len = len(api.portal.get().getPhysicalPath())
        obj_segements = obj.getPhysicalPath()
        relative_path = "/".join(obj_segements[portal_path_len:])
        for schema in iterSchemata(obj):
            for name, field in getFields(schema).items():
                if INamedBlobFileField.providedBy(field) and field.get(obj):
                    index_data[name] = {
                        "path": relative_path,
                        "filename": field.get(obj).filename,
                    }
        return index_data
