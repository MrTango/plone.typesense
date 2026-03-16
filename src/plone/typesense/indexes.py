from datetime import date, datetime
import time
from Acquisition import aq_base, aq_parent
from DateTime import DateTime
from Missing import MV
from plone.folder.nogopip import GopipIndex
from Products.ExtendedPathIndex.ExtendedPathIndex import ExtendedPathIndex
from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex
from Products.PluginIndexes.DateIndex.DateIndex import DateIndex
from Products.PluginIndexes.DateRangeIndex.DateRangeIndex import DateRangeIndex
from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex
from Products.PluginIndexes.util import safe_callable
from Products.PluginIndexes.UUIDIndex.UUIDIndex import UUIDIndex
from Products.ZCTextIndex.ZCTextIndex import ZCTextIndex

from html.parser import HTMLParser

from plone.typesense import log
from plone.typesense.filters import TypesenseFilterBuilder


class HTMLStripper(HTMLParser):
    """Strip HTML tags, returning plain text."""

    def __init__(self):
        super().__init__()
        self._pieces = []

    def handle_data(self, data):
        self._pieces.append(data)

    def get_data(self):
        return " ".join(self._pieces)


def _one(val):
    """
    if list, return first
    otherwise, return value
    """
    if isinstance(val, (list, set, tuple)):
        return val[0]
    return val


def _zdt(val):
    if isinstance(val, datetime):
        val = DateTime(val)
    elif isinstance(val, date):
        val = DateTime(datetime.fromordinal(val.toordinal()))
    elif isinstance(val, str):
        val = DateTime(val)
    return val


def get_index(catalog, name):
    catalog = getattr(catalog, "_catalog", catalog)
    try:
        index = aq_base(catalog.getIndex(name))
    except KeyError:
        return None
    index_type = type(index)
    if index_type in INDEX_MAPPING:
        return INDEX_MAPPING[index_type](catalog, index)
    return None


# Backward-compatible alias used by query.py
getIndex = get_index


class BaseIndex:
    filter_query = True

    def __init__(self, catalog, index):
        self.catalog = catalog
        self.index = index

    def get_value(self, obj):
        value = None
        attrs = self.index.getIndexSourceNames()
        if len(attrs) > 0:
            attr = attrs[0]
        else:
            attr = ""
        if hasattr(self.index, "index_object"):
            value = self.index._get_object_datum(obj, attr)
        else:
            log.info(f"catalogObject was passed bad index object {self.index}.")
        if value == MV:
            return None
        if isinstance(value, list) and len(value) == 0:
            return None
        return value

    def _normalize_query(self, value):
        """Normalize a Plone catalog query value.

        Handles dicts with 'query' key and extracts the actual value.
        """
        if isinstance(value, dict):
            return value.get("query", value)
        return value

    def _detect_negation(self, value):
        """Detect negation in query values.

        Returns (is_negated, clean_value).
        Plone uses 'not' key in query dicts or 'operator': 'not' patterns.
        """
        if isinstance(value, dict):
            if value.get("not"):
                return True, value.get("not")
            if value.get("operator") == "not":
                return True, value.get("query", value)
            return False, value
        return False, value

    def get_ts_filter(self, name, value):
        """Build a Typesense filter_by expression for this index.

        Returns a filter string or None if this index contributes to
        the query string (q) rather than filter_by.
        """
        fb = TypesenseFilterBuilder()
        negated, clean_value = self._detect_negation(value)
        normalized = self._normalize_query(clean_value)

        if isinstance(normalized, (list, tuple)):
            if negated:
                fb.not_equals(name, list(normalized))
            else:
                fb.equals(name, list(normalized))
        else:
            if negated:
                fb.not_equals(name, normalized)
            else:
                fb.equals(name, normalized)
        return fb.build()

    def get_typesense_filter(self, name, value):
        """Backward-compatible alias for get_ts_filter."""
        return self.get_ts_filter(name, value)

    def get_ts_query(self, name, value):
        """Return a dict with Typesense search parameters.

        Keys may include:
          - 'filter_by': a filter string fragment
          - 'q': a query string (for text search indexes)
          - 'query_by': fields to search in (for text search indexes)
          - 'query_by_weights': weight per query_by field

        This is the Typesense-native counterpart of get_query().
        """
        filter_str = self.get_ts_filter(name, value)
        if filter_str:
            return {"filter_by": filter_str}
        return None


class TKeywordIndex(BaseIndex):
    def extract(self, name, data):
        return data[name] or []

    @staticmethod
    def _parse_string_collection(value):
        """Parse a string that looks like a Python list/tuple literal.

        Returns a list of strings if parseable, otherwise None.
        """
        import ast as _ast

        if not isinstance(value, str):
            return None
        stripped = value.strip()
        if (stripped.startswith("[") and stripped.endswith("]")) or \
           (stripped.startswith("(") and stripped.endswith(")")):
            try:
                parsed = _ast.literal_eval(stripped)
                if isinstance(parsed, (list, tuple)):
                    return [str(v) for v in parsed]
            except (ValueError, SyntaxError):
                pass
        return None

    def get_ts_filter(self, name, value):
        """Keywords support list matching and negation."""
        fb = TypesenseFilterBuilder()
        negated, clean_value = self._detect_negation(value)
        normalized = self._normalize_query(clean_value)

        # Handle string representations of lists/tuples
        if isinstance(normalized, str):
            parsed = self._parse_string_collection(normalized)
            if parsed is not None:
                normalized = parsed

        # Keep original collection type — keyword indexes are array-typed
        # so even single-item lists should use list syntax
        is_collection = isinstance(normalized, (list, tuple, set))
        if is_collection:
            vals = list(normalized)
        else:
            vals = [normalized]

        # Use list format if the original input was a collection
        filter_value = vals if is_collection else vals[0]
        if negated:
            fb.not_equals(name, filter_value)
        else:
            fb.equals(name, filter_value)
        return fb.build()


class TFieldIndex(BaseIndex):
    pass


class TDateIndex(BaseIndex):
    """
    """

    missing_date = DateTime("1900/01/01")

    def create_mapping(self, name):
        return {"type": "date", "store": True}

    def get_value(self, obj):
        value = super().get_value(obj)
        if isinstance(value, list):
            if len(value) == 0:
                value = None
            else:
                value = value[0]
        if value in ("None", MV, None, ""):
            value = self.missing_date
        if isinstance(value, str):
            value = DateTime(value)
            utcvalue = value.utcdatetime()
            return int(utcvalue.strftime("%s"))
        if isinstance(value, DateTime):
            utcvalue = value.utcdatetime()
            return int(utcvalue.strftime("%s"))
        return value

    def get_query(self, name, value):
        range_ = value.get("range")
        query = value.get("query")
        if query is None:
            return None
        if range_ is None:
            if type(query) in (list, tuple):
                range_ = "min"

        first = _zdt(_one(query)).ISO8601()
        if range_ == "min":
            return {"range": {name: {"gte": first}}}
        if range_ == "max":
            return {"range": {name: {"lte": first}}}
        if (
            range_ in ("min:max", "minmax")
            and (type(query) in (list, tuple))
            and len(query) == 2
        ):
            return {"range": {name: {"gte": first, "lte": _zdt(query[1]).ISO8601()}}}
        return None

    def get_ts_filter(self, name, value):
        """Date index produces range filters for Typesense."""
        if not isinstance(value, dict):
            # Simple value — exact match as timestamp
            fb = TypesenseFilterBuilder()
            ts_val = self._to_timestamp(value)
            if ts_val is not None:
                fb.equals(name, ts_val)
                return fb.build()
            return None

        range_ = value.get("range")
        query = value.get("query")
        if query is None:
            return None

        if range_ is None:
            if isinstance(query, (list, tuple)):
                range_ = "min"

        fb = TypesenseFilterBuilder()
        first_ts = self._to_timestamp(_one(query))
        if first_ts is None:
            return None

        if range_ == "min":
            fb.greater_equal(name, first_ts)
        elif range_ == "max":
            fb.less_equal(name, first_ts)
        elif range_ in ("min:max", "minmax") and isinstance(query, (list, tuple)) and len(query) == 2:
            second_ts = self._to_timestamp(query[1])
            if second_ts is not None:
                fb.range(name, first_ts, second_ts)
            else:
                fb.greater_equal(name, first_ts)
        else:
            fb.equals(name, first_ts)

        return fb.build() if fb else None

    @staticmethod
    def _to_timestamp(value):
        """Convert a date-like value to a Unix timestamp integer."""
        try:
            dt = _zdt(value)
            if isinstance(dt, DateTime):
                return int(dt.utcdatetime().strftime("%s"))
            return None
        except Exception:
            return None

    def extract(self, name, data):
        try:
            return DateTime(super().extract(name, data))
        except Exception:  # NOQA W0703
            return None


class TZCTextIndex(BaseIndex):
    filter_query = False

    def create_mapping(self, name):
        return {"type": "text", "index": True, "store": False}

    def get_value(self, obj):
        try:
            fields = self.index._indexed_attrs
        except Exception:  # NOQA W0703
            fields = [self.index._fieldname]
        all_texts = []
        for attr in fields:
            text = getattr(obj, attr, None)
            if text is None:
                continue
            if safe_callable(text):
                text = text()
            if text is None:
                continue
            if text:
                if isinstance(
                    text,
                    (
                        list,
                        tuple,
                    ),
                ):
                    all_texts.extend(text)
                else:
                    all_texts.append(text)
        # Check that we're sending only strings
        all_texts = filter(lambda text: isinstance(text, str), all_texts)
        if all_texts:
            return "\n".join(all_texts)
        return None

    def get_query(self, name, value):
        value = self._normalize_query(value)
        # ES doesn't care about * like zope catalog does
        clean_value = value.strip("*") if value else ""
        queries = [{"match_phrase": {name: {"query": clean_value, "slop": 2}}}]
        if name in ("Title", "SearchableText"):
            # titles have most importance... we override here...
            queries.append(
                {"match_phrase_prefix": {"Title": {"query": clean_value, "boost": 2}}}
            )
        if name != "Title":
            queries.append({"match": {name: {"query": clean_value}}})

        return queries

    def get_ts_query(self, name, value):
        """Produce Typesense search parameters for text search.

        Supports:
        - Phrase matching: quoted strings become exact phrase searches
        - Boost for Title when searching SearchableText
        - Negation via 'not' key in query dict
        """
        negated, clean_value = self._detect_negation(value)
        normalized = self._normalize_query(clean_value)

        if isinstance(normalized, str):
            query_text = normalized
        elif isinstance(normalized, (list, tuple)):
            query_text = " ".join(str(v) for v in normalized)
        else:
            query_text = str(normalized)

        # Strip wildcard characters (Plone uses * for prefix searches)
        query_text = query_text.strip("*").strip()

        if not query_text:
            return None

        # If negated, use filter_by with != instead of query
        if negated:
            fb = TypesenseFilterBuilder()
            fb.not_equals(name, query_text)
            return {"filter_by": fb.build()}

        result = {"q": query_text}

        # Detect phrase matching: if the query is wrapped in quotes,
        # keep it as a phrase (Typesense supports quoted phrases in q)
        is_phrase = (
            query_text.startswith('"') and query_text.endswith('"')
        )

        # Build query_by and weights based on the field
        if name in ("Title", "SearchableText"):
            # When searching Title or SearchableText, also search Title
            # with a higher weight for boosting
            if name == "SearchableText":
                result["query_by"] = f"Title,{name}"
                result["query_by_weights"] = "2,1"
            else:
                result["query_by"] = name
                result["query_by_weights"] = "2"
        else:
            result["query_by"] = name

        # Enable infix search for short queries (helps with partial matches)
        if len(query_text) <= 3 and not is_phrase:
            result["infix"] = "always"

        return result


class TBooleanIndex(BaseIndex):
    def create_mapping(self, name):
        return {"type": "boolean"}

    def get_ts_filter(self, name, value):
        """Boolean index filter for Typesense."""
        fb = TypesenseFilterBuilder()
        negated, clean_value = self._detect_negation(value)
        normalized = self._normalize_query(clean_value)

        bool_val = bool(normalized)
        if negated:
            fb.not_equals(name, bool_val)
        else:
            fb.equals(name, bool_val)
        return fb.build()


class TUUIDIndex(BaseIndex):
    pass


class TExtendedPathIndex(BaseIndex):
    filter_query = True

    def create_mapping(self, name):
        return {
            "properties": {
                "path": {"type": "keyword", "index": True, "store": True},
                "depth": {"type": "integer", "store": True},
            }
        }

    def get_value(self, obj):
        attrs = self.index.indexed_attrs
        index = self.index.id if attrs is None else attrs[0]
        path = getattr(obj, index, None)
        if path is not None:
            if safe_callable(path):
                path = path()
            if not isinstance(path, (str, tuple)):
                raise TypeError(
                    f"path value must be string or tuple of "
                    f"strings: ({index}, {repr(path)})"
                )
        else:
            try:
                path = obj.getPhysicalPath()
            except AttributeError:
                return None
        return "/".join(path)

    def extract(self, name, data):
        return data[name]["path"]

    def get_query(self, name, value):
        if isinstance(value, str):
            paths = value
            depth = -1
            navtree = False
            navtree_start = 0
        else:
            depth = value.get("depth", -1)
            paths = value.get("query")
            navtree = value.get("navtree", False)
            navtree_start = value.get("navtree_start", 0)
        if not paths:
            return None
        if isinstance(paths, str):
            paths = [paths]
        andfilters = []
        for path in paths:
            spath = path.split("/")
            gtcompare = "gt"
            start = len(spath) - 1
            if navtree:
                start = start + navtree_start
                end = navtree_start + depth
            else:
                end = start + depth
            if navtree or depth == -1:
                gtcompare = "gte"
            filters = []
            if depth == 0:
                andfilters.append(
                    {"bool": {"filter": {"term": {f"{name}.path": path}}}}
                )
                continue
            filters = [
                {"prefix": {f"{name}.path": path}},
                {"range": {f"{name}.depth": {gtcompare: start}}},
            ]
            if depth != -1:
                filters.append({"range": {f"{name}.depth": {"lte": end}}})
            andfilters.append({"bool": {"must": filters}})
        if len(andfilters) > 1:
            return {"bool": {"should": andfilters}}
        return andfilters[0]

    def get_ts_filter(self, name, value):
        """Path filter for Typesense.

        Typesense doesn't have nested path/depth objects, so we filter
        on the path string field directly. For simple path queries this
        means a prefix-style equality filter on the path string.
        """
        if isinstance(value, str):
            paths = [value]
        elif isinstance(value, dict):
            paths = value.get("query")
            if isinstance(paths, str):
                paths = [paths]
        else:
            return None

        if not paths:
            return None

        fb = TypesenseFilterBuilder()
        for path in paths:
            fb.equals(name, path)

        return fb.build(join="||") if len(paths) > 1 else fb.build()


class TGopipIndex(BaseIndex):
    def create_mapping(self, name):
        return {"type": "integer", "store": True}

    def get_value(self, obj):
        parent = aq_parent(obj)
        if hasattr(parent, "getObjectPosition"):
            return parent.getObjectPosition(obj.getId())
        return None


class TDateRangeIndex(BaseIndex):
    def create_mapping(self, name):
        return {
            "properties": {
                f"{name}1": {"type": "date", "store": True},
                f"{name}2": {"type": "date", "store": True},
            }
        }

    def get_value(self, obj):
        if self.index._since_field is None:
            return None
        since = getattr(obj, self.index._since_field, None)
        if safe_callable(since):
            since = since()
        until = getattr(obj, self.index._until_field, None)
        if safe_callable(until):
            until = until()
        if not since or not until:
            return None
        return {
            f"{self.index.id}1": since.strftime("%s"),
            f"{self.index.id}2": until.strftime("%s"),
        }

    def get_query(self, name, value):
        value = self._normalize_query(value)
        date_iso = value.ISO8601()
        return [
            {"range": {f"{name}.{name}1": {"lte": date_iso}}},
            {"range": {f"{name}.{name}2": {"gte": date_iso}}},
        ]

    def get_ts_filter(self, name, value):
        """Date range index for Typesense.

        The 'since' field must be <= value and 'until' field >= value.
        """
        normalized = self._normalize_query(value)
        ts_val = TDateIndex._to_timestamp(normalized)
        if ts_val is None:
            return None

        fb = TypesenseFilterBuilder()
        fb.less_equal(f"{name}1", ts_val)
        fb.greater_equal(f"{name}2", ts_val)
        return fb.build()


class TRecurringIndex(TDateIndex):
    pass


INDEX_MAPPING = {
    KeywordIndex: TKeywordIndex,
    FieldIndex: TFieldIndex,
    DateIndex: TDateIndex,
    ZCTextIndex: TZCTextIndex,
    BooleanIndex: TBooleanIndex,
    UUIDIndex: TUUIDIndex,
    ExtendedPathIndex: TExtendedPathIndex,
    GopipIndex: TGopipIndex,
    DateRangeIndex: TDateRangeIndex,
}

try:
    from Products.DateRecurringIndex.index import DateRecurringIndex  # NOQA C0412

    INDEX_MAPPING[DateRecurringIndex] = TRecurringIndex
except ImportError:
    pass
