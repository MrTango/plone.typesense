from datetime import date, datetime
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

from plone.typesense import log


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

    def get_typesense_filter(self, name, value):
        """Convert Plone query to Typesense filter_by syntax.

        Returns a filter string like 'field:=value' or None if no filter.
        """
        return None

    def get_typesense_query(self, name, value):
        """Convert Plone query to Typesense query parameters (q, query_by).

        Returns a dict with 'q' and 'query_by' or None.
        """
        return None

    def _normalize_query(self, value):
        """Normalize query value from various formats."""
        if isinstance(value, dict):
            return value.get('query', value)
        return value


class TKeywordIndex(BaseIndex):
    def extract(self, name, data):
        return data[name] or []

    def get_typesense_filter(self, name, value):
        """Convert keyword query to Typesense filter.

        Examples:
          portal_type='Document' -> 'portal_type:=Document'
          portal_type=['Document', 'News Item'] -> 'portal_type:[Document, `News Item`]'
        """
        if isinstance(value, (list, tuple, set)):
            # Escape values with spaces using backticks
            escaped_values = [f'`{v}`' if ' ' in str(v) else str(v) for v in value]
            return f"{name}:[{', '.join(escaped_values)}]"
        else:
            # Single value - exact match
            val = f'`{value}`' if ' ' in str(value) else str(value)
            return f"{name}:={val}"


class TFieldIndex(BaseIndex):
    def get_typesense_filter(self, name, value):
        """Convert field query to Typesense filter.

        Examples:
          Type='Document' -> 'Type:=Document'
        """
        val = f'`{value}`' if ' ' in str(value) else str(value)
        return f"{name}:={val}"


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

    def get_typesense_filter(self, name, value):
        """Convert date query to Typesense filter.

        Examples:
          created={'query': dt, 'range': 'min'} -> 'created:>=1234567890'
          created={'query': dt, 'range': 'max'} -> 'created:<=1234567890'
          created={'query': [dt1, dt2], 'range': 'min:max'} -> 'created:>=1234567890 && created:<=1234567899'
        """
        if isinstance(value, dict):
            range_ = value.get("range")
            query = value.get("query")
        else:
            # Simple date value
            query = value
            range_ = None

        if query is None:
            return None

        if range_ is None:
            if isinstance(query, (list, tuple)):
                range_ = "min"

        # Convert to timestamp
        first_dt = _zdt(_one(query))
        first_ts = int(first_dt.utcdatetime().strftime("%s"))

        if range_ == "min":
            return f"{name}:>={first_ts}"
        if range_ == "max":
            return f"{name}:<={first_ts}"
        if range_ in ("min:max", "minmax") and isinstance(query, (list, tuple)) and len(query) == 2:
            second_dt = _zdt(query[1])
            second_ts = int(second_dt.utcdatetime().strftime("%s"))
            return f"{name}:>={first_ts} && {name}:<={second_ts}"

        # Default: exact match
        return f"{name}:={first_ts}"

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

    def get_typesense_query(self, name, value):
        """Convert text search to Typesense query parameters.

        Returns dict with 'q' (search text) and 'query_by' (fields to search).
        """
        value = self._normalize_query(value)
        # Strip wildcards - Typesense handles fuzzy/infix matching via schema
        clean_value = value.strip("*") if value else ""

        if not clean_value:
            return None

        # Build query_by list - search in the requested field
        query_by_fields = [name]

        # For SearchableText, also search Title with higher weight
        if name == "SearchableText":
            query_by_fields = ["Title", "SearchableText"]

        return {
            'q': clean_value,
            'query_by': ','.join(query_by_fields)
        }


class TBooleanIndex(BaseIndex):
    def create_mapping(self, name):
        return {"type": "boolean"}

    def get_typesense_filter(self, name, value):
        """Convert boolean query to Typesense filter.

        Examples:
          is_folderish=True -> 'is_folderish:=true'
          is_folderish=False -> 'is_folderish:=false'
        """
        bool_val = 'true' if value else 'false'
        return f"{name}:={bool_val}"


class TUUIDIndex(BaseIndex):
    def get_typesense_filter(self, name, value):
        """Convert UUID query to Typesense filter.

        Examples:
          UID='abc123' -> 'UID:=abc123'
        """
        return f"{name}:={value}"


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
        return data[name]

    def get_typesense_filter(self, name, value):
        """Convert path query to Typesense filter.

        Examples:
          path='/folder' -> 'path:=/folder*'
          path={'query': '/folder', 'depth': 0} -> 'path:=/folder'
          path={'query': '/folder', 'depth': 1} -> 'path:=/folder* && depth:<=2'
          path={'query': ['/a', '/b']} -> 'path:=/a* || path:=/b*'
        """
        if isinstance(value, str):
            paths = [value]
            depth = -1
        else:
            depth = value.get("depth", -1)
            paths = value.get("query")
            if isinstance(paths, str):
                paths = [paths]

        if not paths:
            return None

        # Build filter for each path
        path_filters = []
        for path in paths:
            spath = path.split("/")
            path_depth = len(spath) - 1

            if depth == 0:
                # Exact path match
                path_filters.append(f"path:={path}")
            elif depth == -1:
                # All descendants (unlimited depth)
                path_filters.append(f"path:={path}*")
            else:
                # Limited depth
                max_depth = path_depth + depth
                path_filters.append(f"(path:={path}* && depth:<={max_depth})")

        # Combine multiple paths with OR
        if len(path_filters) > 1:
            return '(' + ' || '.join(path_filters) + ')'
        return path_filters[0]


class TGopipIndex(BaseIndex):
    def create_mapping(self, name):
        return {"type": "integer", "store": True}

    def get_value(self, obj):
        parent = aq_parent(obj)
        if hasattr(parent, "getObjectPosition"):
            return parent.getObjectPosition(obj.getId())
        return None

    def get_typesense_filter(self, name, value):
        """Convert gopip (position) query to Typesense filter.

        Examples:
          getObjPositionInParent=5 -> 'getObjPositionInParent:=5'
          getObjPositionInParent={'query': 5, 'range': 'min'} -> 'getObjPositionInParent:>=5'
        """
        if isinstance(value, dict):
            range_ = value.get("range")
            query = value.get("query")
            if range_ == "min":
                return f"{name}:>={query}"
            elif range_ == "max":
                return f"{name}:<={query}"
            else:
                return f"{name}:={query}"
        return f"{name}:={value}"


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

    def get_typesense_filter(self, name, value):
        """Convert date range query to Typesense filter.

        Checks if value falls within the range defined by two date fields.
        Examples:
          effective_range=DateTime() -> 'effective_range1:<=1234567890 && effective_range2:>=1234567890'
        """
        value = self._normalize_query(value)
        if isinstance(value, str):
            value = DateTime(value)
        timestamp = int(value.utcdatetime().strftime("%s"))
        return f"{name}1:<={timestamp} && {name}2:>={timestamp}"


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



