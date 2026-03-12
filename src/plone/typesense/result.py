from Acquisition import aq_base
from Acquisition import aq_get
from Acquisition import aq_parent
from plone.typesense import interfaces
from plone.typesense.utils import get_brain_from_path
from Products.ZCatalog.CatalogBrains import AbstractCatalogBrain
from Products.ZCatalog.interfaces import ICatalogBrain
from typing import Union
from zope.component import getMultiAdapter
from zope.globalrequest import getRequest
from zope.interface import implementer
from ZPublisher.BaseRequest import RequestContainer


@implementer(ICatalogBrain)
class TypesenseBrain:
    """A Brain containing only information indexed in Typesense."""

    def __init__(self, record: dict, catalog):
        self._record = record
        self._catalog = catalog

    def has_key(self, key):
        return key in self._record

    def __contains__(self, name):
        return name in self._record

    def __getattr__(self, name):
        if not self.__contains__(name):
            raise AttributeError(
                f"'TypesenseBrain' object has no attribute '{name}'"
            )
        return self._record[name]

    def getPath(self):
        """Get the physical path for this record"""
        return self._record["path"]

    def getURL(self, relative=0):
        """Generate a URL for this record"""
        request = getRequest()
        return request.physicalPathToURL(self.getPath(), relative)

    def getObject(self, REQUEST=None):
        path = self.getPath().split("/")
        if not path:
            return None
        parent = aq_parent(self._catalog)
        if aq_get(parent, "REQUEST", None) is None:
            request = getRequest()
            if request is not None:
                # path should be absolute, starting at the physical root
                parent = self.getPhysicalRoot()
                request_container = RequestContainer(REQUEST=request)
                parent = aq_base(parent).__of__(request_container)
        if len(path) > 1:
            parent = parent.unrestrictedTraverse(path[:-1])

        return parent.restrictedTraverse(path[-1])

    def getRID(self) -> int:
        """Return the record ID for this object."""
        return -1


def BrainFactory(manager):
    def factory(hit: dict) -> Union[AbstractCatalogBrain, TypesenseBrain]:
        """Convert Typesense hit to catalog brain.

        @param hit: Typesense hit with 'document' containing indexed fields
        """
        print(f"\n[BrainFactory.factory] CALLED with hit keys: {hit.keys() if isinstance(hit, dict) else type(hit)}", flush=True)
        catalog = manager.catalog
        zcatalog = catalog._catalog

        # Typesense returns hits with 'document' field containing the actual data
        document = hit.get("document", {})
        path = document.get("path", None)

        if path:
            print(f"\n[BrainFactory] path={path}", flush=True)
            brain = get_brain_from_path(zcatalog, path)
            print(f"[BrainFactory] brain from catalog={brain}, type={type(brain)}", flush=True)
            if not brain:
                # Create TypesenseBrain from document data
                print(f"[BrainFactory] Creating TypesenseBrain from document", flush=True)
                brain = TypesenseBrain(record=document, catalog=catalog)
            else:
                print(f"[BrainFactory] Using catalog brain, has Title: {hasattr(brain, 'Title')}", flush=True)
                if hasattr(brain, 'Title'):
                    print(f"[BrainFactory] brain.Title={brain.Title}", flush=True)

            # Handle highlighting if enabled
            try:
                if manager.highlight and hit.get("highlight"):
                    fragments = []
                    fraglen = 0
                    for idx, i in enumerate(hit["highlight"].get("SearchableText", [])):
                        fraglen += len(i)
                        if idx > 0 and fraglen > manager.highlight_threshold:
                            break
                        fragments.append(i)
                    brain["Description"] = " ... ".join(fragments)
            except Exception as e:
                print(f"[BrainFactory] ERROR in highlighting: {e}", flush=True)
                import traceback
                traceback.print_exc()

            print(f"[BrainFactory] Returning brain: {brain}", flush=True)
            return brain
        return None

    return factory


class TypesenseResult:
    def __init__(self, manager, query, **query_params):
        print(f"\n[TypesenseResult.__init__] START - query={query}", flush=True)
        assert "sort" not in query_params
        assert "start" not in query_params
        print(f"[TypesenseResult.__init__] Asserts passed", flush=True)
        self.manager = manager
        print(f"[TypesenseResult.__init__] Manager set", flush=True)
        self.bulk_size = manager.bulk_size
        print(f"[TypesenseResult.__init__] bulk_size={self.bulk_size}", flush=True)
        print(f"\n[TypesenseResult] About to get QueryAssembler adapter", flush=True)
        print(f"[TypesenseResult] request={getRequest()}, manager={manager}", flush=True)
        try:
            qassembler = getMultiAdapter(
                (getRequest(), manager), interfaces.IQueryAssembler
            )
            print(f"[TypesenseResult] Got QueryAssembler: {qassembler}", flush=True)
        except Exception as e:
            print(f"[TypesenseResult] ERROR getting adapter: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise
        dquery, self.sort = qassembler.normalize(query)
        self.query = qassembler(dquery)

        # results are stored in a dictionary, keyed
        # by the start index of the bulk size for the
        # results it holds. This way we can skip around
        # for result data in a result object
        result = manager._search(self.query, sort=self.sort)
        self.results = {0: result["hits"]}
        self.count = result["found"]
        self.query_params = query_params

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        """
        Lazy loading TS results with negative index support.
        We store the results in buckets of what the bulk size is.
        This is so you can skip around in the indexes without needing
        to load all the data.
        Example(all zero based indexing here remember):
            (525 results with bulk size 50)
            - self[0]: 0 bucket, 0 item
            - self[10]: 0 bucket, 10 item
            - self[50]: 50 bucket: 0 item
            - self[55]: 50 bucket: 5 item
            - self[352]: 350 bucket: 2 item
            - self[-1]: 500 bucket: 24 item
            - self[-2]: 500 bucket: 23 item
            - self[-55]: 450 bucket: 19 item
        """
        print(f"\n[TypesenseResult.__getitem__] key={key}, count={self.count}, results keys={list(self.results.keys())}", flush=True)
        bulk_size = self.bulk_size
        count = self.count
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.end)]
        if key + 1 > count:
            raise IndexError
        if key < 0 and abs(key) > count:
            raise IndexError
        if key >= 0:
            result_key = int(key / bulk_size) * bulk_size
            start = result_key
            result_index = key % bulk_size
        elif key < 0:
            last_key = int(count / bulk_size) * bulk_size
            last_key = last_key if last_key else count
            start = result_key = int(last_key - ((abs(key) / bulk_size) * bulk_size))
            if last_key == result_key:
                result_index = key
            else:
                result_index = (key % bulk_size) - (bulk_size - (count % last_key))
        if result_key not in self.results:
            result = self.manager._search(
                self.query, sort=self.sort, start=start
            )
            self.results[result_key] = result["hits"]
        print(f"[TypesenseResult.__getitem__] result_key={result_key}, result_index={result_index}", flush=True)
        print(f"[TypesenseResult.__getitem__] self.results[{result_key}] = {self.results[result_key]}", flush=True)
        item = self.results[result_key][result_index]
        print(f"[TypesenseResult.__getitem__] Returning item: {item}", flush=True)
        return item
