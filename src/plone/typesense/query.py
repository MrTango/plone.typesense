from plone.typesense import log
from plone.typesense.indexes import TZCTextIndex
from plone.typesense.indexes import get_index
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
            # Skip fields that are part of other queries or don't belong in Typesense
            # 'depth' is handled as part of path queries, not a separate field
            if key in ['depth']:
                continue

            if key not in idxs and key not in ts_only_indexes:
                continue

            index = get_index(catalog, key)
            if index is None and key in ts_only_indexes:
                # deleted index for plone performance but still need on TS
                # Create a mock index object with all required attributes
                class MockIndex:
                    def __init__(self, index_id):
                        self.id = index_id
                        self._fieldname = index_id

                        # For SearchableText, specify all fields that should be indexed
                        # This mimics Plone's real SearchableText index configuration
                        if index_id == 'SearchableText':
                            self._indexed_attrs = ['Title', 'Description', 'text', 'id']
                        else:
                            self._indexed_attrs = None

                    def getIndexSourceNames(self):
                        if self._indexed_attrs:
                            return self._indexed_attrs
                        return [self.id]

                    def __repr__(self):
                        return f"<MockIndex {self.id}>"

                mock_index = MockIndex(key)
                index = TZCTextIndex(catalog, mock_index)

            if index is None:
                continue

            # Check if this is a filter first (exact match preferred over text search)
            if hasattr(index, 'get_typesense_filter'):
                try:
                    ts_filter = index.get_typesense_filter(key, value)
                    if ts_filter:
                        filters.append(ts_filter)
                        log.debug(f"Added Typesense filter for {key}: {ts_filter}")
                        # If we have a filter, skip the text query for this field
                        continue
                    else:
                        log.debug(f"No filter returned for {key}={value}")
                except Exception as e:
                    log.error(f"Error getting Typesense filter for {key}: {e}", exc_info=True)
                    raise

            # Check if this is a text search query (only if no filter was applied)
            if hasattr(index, 'get_typesense_query'):
                try:
                    ts_query = index.get_typesense_query(key, value)
                    if ts_query:
                        # Text queries return {'q': '...', 'query_by': '...'}
                        text_query = ts_query.get('q', text_query)
                        if ts_query.get('query_by'):
                            query_by_fields.append(ts_query['query_by'])
                        log.debug(f"Added Typesense query for {key}: {ts_query}")
                except Exception as e:
                    log.error(f"Error getting Typesense query for {key}: {e}", exc_info=True)
                    raise

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
            log.info(f"QueryAssembler: Combined filters list: {filters}")
            log.info(f"QueryAssembler: Final filter_by string: {params['filter_by']}")

        log.info(f"QueryAssembler: Generated Typesense params: {params}")
        return params
