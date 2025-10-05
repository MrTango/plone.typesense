from plone.typesense.indexes import TZCTextIndex
from plone.typesense.indexes import getIndex
from plone.typesense.interfaces import IQueryAssembler
from plone.typesense.utils import get_ts_only_indexes
from zope.interface import implementer


@implementer(IQueryAssembler)
class QueryAssembler:
    def __init__(self, request, manager):
        self.catalog = manager.catalog
        self.request = request

    def normalize(self, query):  # NOQA R0201
        sort_on = []
        sort = query.pop("sort_on", None)
        # default plone is ascending
        sort_order = query.pop("sort_order", "asc")
        if sort_order in ("descending", "reverse", "desc"):
            sort_order = "desc"
        else:
            sort_order = "asc"

        if sort:
            for sort_str in sort.split(","):
                sort_on.append({sort_str: {"order": sort_order}})
        if "b_size" in query:
            del query["b_size"]
        if "b_start" in query:
            del query["b_start"]
        if "sort_limit" in query:
            del query["sort_limit"]
        return query, sort_on

    def __call__(self, dquery):
        """Build Typesense search parameters from Plone query dict.

        Returns dict with:
        - 'q': search text
        - 'query_by': fields to search in
        - 'filter_by': filter expression
        - 'sort_by': sorting expression
        """
        catalog = self.catalog._catalog
        idxs = catalog.indexes.keys()
        ts_only_indexes = get_ts_only_indexes()

        # Collect filters and text queries separately
        filters = []
        text_query = None
        query_by_fields = []

        for key, value in dquery.items():
            if key not in idxs and key not in ts_only_indexes:
                continue

            index = getIndex(catalog, key)
            if index is None and key in ts_only_indexes:
                # deleted index for plone performance but still need on TS
                index = TZCTextIndex(catalog, key)

            if index is None:
                continue

            # Check if this is a text search query
            if hasattr(index, 'get_typesense_query'):
                ts_query = index.get_typesense_query(key, value)
                if ts_query:
                    # Text queries return {'q': '...', 'query_by': '...'}
                    text_query = ts_query.get('q', text_query)
                    if ts_query.get('query_by'):
                        query_by_fields.append(ts_query['query_by'])

            # Check if this is a filter
            if hasattr(index, 'get_typesense_filter'):
                ts_filter = index.get_typesense_filter(key, value)
                if ts_filter:
                    filters.append(ts_filter)

        # Build Typesense search parameters
        params = {}

        # Add text search if present
        if text_query:
            params['q'] = text_query
            params['query_by'] = ','.join(query_by_fields) if query_by_fields else 'SearchableText'
        else:
            # Typesense requires 'q' parameter, use '*' for match-all
            params['q'] = '*'

        # Add filters
        if filters:
            params['filter_by'] = ' && '.join(filters)

        return params
