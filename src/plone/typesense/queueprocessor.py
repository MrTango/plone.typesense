from plone.app.uuid.utils import uuidToObject
from plone.dexterity.utils import iterSchemata
from plone.indexer.interfaces import IIndexableObject, IIndexer
from plone.namedfile.interfaces import INamedBlobFileField
from zope.component import getUtility, queryMultiAdapter
from zope.interface import implementer
from zope.schema import getFields

from plone import api
from plone.typesense import log
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from plone.typesense.indexes import get_index
from plone.typesense.interfaces import (
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
        from pprint import pprint
        pprint(objects)
        self.ts_connector.index(objects)

    def ts_update(self, objects):
        """update indexed objects in Typesense"""
        from pprint import pprint
        pprint(objects)
        self.ts_connector.update(objects)

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
            print(f"found obj: {obj.id}")
        wrapped_object = self.wrap_object(obj)
        attributes = attributes if attributes else self.all_attributes
        catalog = self.catalog
        for index_name in attributes:
            value = None
            index = get_index(catalog, index_name)
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
            index_data[index_name] = value

        # additional_providers = [
        #     adapter for adapter in getAdapters((obj,), IAdditionalIndexDataProvider)
        # ]
        # if additional_providers:
        #     for _, adapter in additional_providers:
        #         index_data.update(adapter(catalog, index_data))
        print(f"index_data:\n {index_data}")
        return index_data

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
            return
        return False
        # return IReindexActive.providedBy(getRequest())

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
            attributes = {att for att in attributes} if attributes else set()
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
        print(f"reindex: {obj.id}: {attributes}")
        self.index(obj, attributes)

    def unindex(self, obj):
        """queue an unindex operation for the given object"""
        if not self.active:
            return
        print(f"unindex: {obj.id}")

    def begin(self,):
        """called before processing of the queue is started"""
        print(f"begin()")

    def commit(self, wait=None):
        """called after processing of the queue has ended"""
        print("commit()")
        self.commit_ts()

    def commit_ts(self, wait=None):
        """Transaction commit."""
        if not self.active:
            return
        actions = self.actions
        items = len(actions) if actions else 0
        if self.ts_client and items:
            ts_data = {}
            from pprint import pprint
            data = actions.all()
            pprint(data)
            for action, uuid, payload in data:
                payload = self._prepare_for_typesense(uuid, payload)
                pprint(payload)
                if action not in ts_data:
                    ts_data[action] = []
                ts_data[action].append(payload)
            print(f"actions: {ts_data.keys()}")
            self.ts_index(ts_data["index"])
            self.ts_update(ts_data["update"])
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
        print(f"abort()")

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
