from plone.typesense.indexes import TZCTextIndex
from plone.typesense.indexes import get_index
from plone.typesense.interfaces import IQueryAssembler
from plone.typesense.utils import get_ts_only_indexes
from zope.interface import implementer

# Backward-compatible alias
getIndex = get_index


@implementer(IQueryAssembler)
class QueryAssembler:
    def __init__(self, request, manager):
        # self.es = manager
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
        sort_on.append("_score")
        if "b_size" in query:
            del query["b_size"]
        if "b_start" in query:
            del query["b_start"]
        if "sort_limit" in query:
            del query["sort_limit"]
        return query, sort_on

    def __call__(self, dquery):
        filters = []
        matches = []
        catalog = self.catalog._catalog
        idxs = catalog.indexes.keys()
        query = {"match_all": {}}
        ts_only_indexes = get_ts_only_indexes()
        for key, value in dquery.items():
            if key not in idxs and key not in ts_only_indexes:
                continue
            index = get_index(catalog, key)
            if index is None and key in ts_only_indexes:
                # deleted index for plone performance but still need on TS
                index = TZCTextIndex(catalog, key)
            qq = index.get_query(key, value)
            if qq is None:
                continue
            if index is not None and index.filter_query:
                if isinstance(qq, list):
                    filters.extend(qq)
                else:
                    filters.append(qq)
            else:
                if isinstance(qq, list):
                    matches.extend(qq)
                else:
                    matches.append(qq)
        if len(filters) == 0 and len(matches) == 0:
            return query
        query = {"bool": {}}
        if len(filters) > 0:
            query["bool"]["filter"] = filters

        if len(matches) > 0:
            query["bool"]["should"] = matches
            query["bool"]["minimum_should_match"] = 1
        return query


class TypesenseQueryAssembler:
    """Assembles Plone catalog queries into Typesense search parameters.

    Unlike QueryAssembler which produces Elasticsearch-style dicts,
    this assembler produces Typesense-native parameters:
    - filter_by: string filters joined with &&
    - q: the search query text
    - query_by: comma-separated field names to search
    - query_by_weights: comma-separated weights
    - sort_by: Typesense sort string
    """

    def __init__(self, request, manager):
        self.catalog = manager.catalog
        self.request = request

    def normalize(self, query):
        """Extract and normalize sort parameters from the query.

        Returns (query, sort_by_string).
        """
        sort_parts = []
        sort = query.pop("sort_on", None)
        sort_order = query.pop("sort_order", "asc")
        if sort_order in ("descending", "reverse", "desc"):
            sort_order = "desc"
        else:
            sort_order = "asc"

        if sort:
            for sort_str in sort.split(","):
                sort_parts.append(f"{sort_str}:{sort_order}")

        # Default sort by text relevance score
        sort_parts.append("_text_match:desc")

        sort_by = ",".join(sort_parts)

        # Remove pagination params (handled separately)
        query.pop("b_size", None)
        query.pop("b_start", None)
        query.pop("sort_limit", None)

        return query, sort_by

    def __call__(self, dquery):
        """Assemble a Typesense search parameter dict from a Plone query.

        Returns a dict with keys like:
        - 'q': search query text (default '*' for match-all)
        - 'filter_by': combined filter string
        - 'query_by': fields to search in
        - 'query_by_weights': weights for query_by fields
        - 'sort_by': sort specification
        - 'infix': infix search mode
        """
        filter_parts = []
        q_parts = []
        query_by_fields = []
        query_by_weights = []
        infix_mode = None

        catalog = self.catalog._catalog
        idxs = catalog.indexes.keys()
        ts_only_indexes = get_ts_only_indexes()

        for key, value in dquery.items():
            if key not in idxs and key not in ts_only_indexes:
                continue

            index = get_index(catalog, key)
            if index is None and key in ts_only_indexes:
                index = TZCTextIndex(catalog, key)
            if index is None:
                continue

            ts_params = index.get_ts_query(key, value)
            if ts_params is None:
                continue

            # Collect filter_by parts
            if "filter_by" in ts_params:
                filter_parts.append(ts_params["filter_by"])

            # Collect query text
            if "q" in ts_params:
                q_parts.append(ts_params["q"])

            # Collect query_by fields and weights
            if "query_by" in ts_params:
                fields = ts_params["query_by"].split(",")
                weights = (
                    ts_params.get("query_by_weights", "")
                    .split(",") if "query_by_weights" in ts_params else []
                )
                for i, field in enumerate(fields):
                    if field not in query_by_fields:
                        query_by_fields.append(field)
                        weight = weights[i] if i < len(weights) else "1"
                        query_by_weights.append(weight)

            # Collect infix mode
            if "infix" in ts_params:
                infix_mode = ts_params["infix"]

        # Build final search parameters
        result = {}

        if q_parts:
            # Combine multiple query texts (rare, but handle it)
            result["q"] = " ".join(q_parts)
        else:
            result["q"] = "*"

        if filter_parts:
            result["filter_by"] = " && ".join(filter_parts)

        if query_by_fields:
            result["query_by"] = ",".join(query_by_fields)
            result["query_by_weights"] = ",".join(query_by_weights)

        if infix_mode:
            result["infix"] = infix_mode

        return result
