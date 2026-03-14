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
        return self._record["path"]["path"]

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
    def factory(result: dict) -> Union[AbstractCatalogBrain, TypesenseBrain]:
        catalog = manager.catalog
        zcatalog = catalog._catalog
        path = result.get("fields", {}).get("path.path", None)
        if type(path) in (list, tuple, set) and len(path) > 0:
            path = path[0]
        if path:
            brain = get_brain_from_path(zcatalog, path)
            if not brain:
                result = manager.get_record_by_path(path)
                brain = TypesenseBrain(record=result, catalog=catalog)
            if manager.highlight and result.get("highlight"):
                fragments = []
                fraglen = 0
                for idx, i in enumerate(result["highlight"].get("SearchableText", [])):
                    fraglen += len(i)
                    if idx > 0 and fraglen > manager.highlight_threshold:
                        break
                    fragments.append(i)
                brain["Description"] = " ... ".join(fragments)
            return brain
        # We should handle cases where there is no path in the ES response
        return None

    return factory


class FacetResult:
    """Container for search results with facet/aggregation data.

    Attributes
    ----------
    results : LazyMap
        The search result brains.
    facet_counts : dict
        Facet counts keyed by field name.  Each value is a list of
        ``{"value": str, "count": int}`` dicts as returned by Typesense,
        normalized for easy consumption.
    count : int
        Total number of matching documents.
    """

    def __init__(self, results, facet_counts, count):
        self.results = results
        self.count = count
        self._raw_facet_counts = facet_counts
        self.facet_counts = self._normalize_facets(facet_counts)

    @staticmethod
    def _normalize_facets(raw_facet_counts):
        """Normalize Typesense facet_counts into a simple dict.

        Typesense returns::

            [
                {
                    "field_name": "portal_type",
                    "counts": [
                        {"value": "Document", "count": 42},
                        {"value": "News Item", "count": 7},
                    ],
                    "stats": {...},
                },
                ...
            ]

        This method transforms it to::

            {
                "portal_type": [
                    {"value": "Document", "count": 42},
                    {"value": "News Item", "count": 7},
                ],
                ...
            }
        """
        if not raw_facet_counts:
            return {}
        result = {}
        for facet in raw_facet_counts:
            field_name = facet.get("field_name", "")
            counts = facet.get("counts", [])
            result[field_name] = [
                {"value": c.get("value", ""), "count": c.get("count", 0)}
                for c in counts
            ]
        return result

    def get_facet_values(self, field_name):
        """Get facet values for a specific field.

        Returns a list of {"value": str, "count": int} dicts,
        or an empty list if the field was not faceted.
        """
        return self.facet_counts.get(field_name, [])

    def __len__(self):
        return self.count


class TypesenseResult:
    def __init__(self, manager, query, **query_params):
        assert "sort" not in query_params
        assert "start" not in query_params
        self.manager = manager
        self.bulk_size = manager.bulk_size
        qassembler = getMultiAdapter(
            (getRequest(), manager), interfaces.IQueryAssembler
        )
        dquery, self.sort = qassembler.normalize(query)
        self.query = qassembler(dquery)

        # results are stored in a dictionary, keyed
        # but the start index of the bulk size for the
        # results it holds. This way we can skip around
        # for result data in a result object
        raw_result = manager._search(self.query, sort=self.sort, **query_params)
        self.results = {0: raw_result["hits"]}
        self.count = raw_result["found"]
        self.query_params = query_params

        # Store facet counts if present (populated by faceted_search)
        self.facet_counts = raw_result.get("facet_counts", [])

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
        bulk_size = self.bulk_size
        count = self.count
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.stop)]
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
            self.results[result_key] = self.manager._search(
                self.query, sort=self.sort, start=start, **self.query_params
            )["hits"]
        return self.results[result_key][result_index]
