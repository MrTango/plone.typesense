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


def _parse_value(value):
    """Parse query value, converting string representations of lists/tuples into actual lists.

    When query parameters come from HTTP requests or URLs, list values are often
    passed as string representations like "['Document', 'News Item']".
    This function detects and parses such strings back into Python lists.

    Examples:
        "['Document', 'News Item']" -> ['Document', 'News Item']
        "('Document', 'News Item')" -> ['Document', 'News Item']
        "Document" -> "Document" (unchanged)
        ['Document', 'News Item'] -> ['Document', 'News Item'] (unchanged)

    @param value: The value to parse
    @return: Parsed value (list if string representation detected, otherwise unchanged)
    """
    if not isinstance(value, str):
        return value

    # Check if it looks like a list or tuple string representation
    stripped = value.strip()
    if (stripped.startswith('[') and stripped.endswith(']')) or \
       (stripped.startswith('(') and stripped.endswith(')')):
        try:
            # Use ast.literal_eval for safe parsing (no code execution)
            import ast
            parsed = ast.literal_eval(stripped)
            # literal_eval can return various types, make sure it's a sequence
            if isinstance(parsed, (list, tuple)):
                return list(parsed)  # Always return as list for consistency
        except (ValueError, SyntaxError):
            # If parsing fails, return original value
            pass

    return value


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
          portal_type='Document' -> 'portal_type:=`Document`'
          portal_type=['Document', 'News Item'] -> 'portal_type:[`Document`, `News Item`]'
          portal_type={'query': ['Document', 'News Item'], 'operator': 'or'} -> 'portal_type:[`Document`, `News Item`]'

        Handles string representations of lists from URL parameters:
          portal_type="['Document', 'News Item']" -> 'portal_type:[`Document`, `News Item`]'

        Note: ALL string values are wrapped in backticks as per Typesense filter syntax.
        """
        log.info(f"TKeywordIndex.get_typesense_filter CALLED: name={name}, value={value}, type={type(value)}")

        # Normalize query - extract 'query' from dict if present
        value = self._normalize_query(value)
        log.info(f"TKeywordIndex after _normalize_query: value={value}, type={type(value)}")

        # Parse string representations of lists/tuples into actual lists
        # This handles cases where query params come from URLs like "?portal_type=['Document', 'News Item']"
        value = _parse_value(value)
        log.info(f"TKeywordIndex after _parse_value: value={value}, type={type(value)}")

        if isinstance(value, (list, tuple, set)):
            # Wrap ALL string values in backticks (Typesense filter syntax requirement)
            escaped_values = [f'`{v}`' for v in value]
            log.info(f"TKeywordIndex escaped_values list: {escaped_values}")
            result = f"{name}:[{', '.join(escaped_values)}]"
            log.info(f"TKeywordIndex RETURNING filter for list: {result}")
            return result
        else:
            # Single value - exact match - wrap in backticks
            result = f"{name}:=`{value}`"
            log.info(f"TKeywordIndex RETURNING filter for single value: {result}")
            return result


class TFieldIndex(BaseIndex):
    def get_typesense_filter(self, name, value):
        """Convert field query to Typesense filter.

        Examples:
          Type='Document' -> 'Type:=`Document`'
          Type={'query': 'Document'} -> 'Type:=`Document`'

        Note: ALL string values are wrapped in backticks as per Typesense filter syntax.
        """
        # Normalize query - extract 'query' from dict if present
        value = self._normalize_query(value)

        # Wrap in backticks (Typesense filter syntax requirement)
        return f"{name}:=`{value}`"


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
        """Extract indexable text value from object.

        For SearchableText, this method manually extracts text from Title, Description,
        and body text fields (like 'text') to ensure complete indexing. This is necessary
        because IIndexer adapters may return cached data that doesn't include body text.

        For other text indexes, it uses the standard extraction via getattr or IIndexer.
        """
        try:
            fields = self.index._indexed_attrs
        except Exception:  # NOQA W0703
            fields = [self.index._fieldname]

        all_texts = []
        for attr in fields:
            # For SearchableText, manually extract from object fields to ensure body text is included
            if attr == 'SearchableText':
                # Get the original object from wrapper if needed
                original_obj = obj.object if hasattr(obj, 'object') else obj

                # Build SearchableText from ID + Title + Description + body text
                parts = []

                # Get ID
                if hasattr(original_obj, 'id'):
                    parts.append(str(original_obj.id))

                # Get Title
                if hasattr(original_obj, 'Title'):
                    title = original_obj.Title
                    if safe_callable(title):
                        title = title()
                    if title:
                        parts.append(str(title))

                # Get Description
                if hasattr(original_obj, 'Description'):
                    desc = original_obj.Description
                    if safe_callable(desc):
                        desc = desc()
                    if desc:
                        parts.append(str(desc))

                # Get body text from 'text' field (RichText for Documents)
                if hasattr(original_obj, 'text') and original_obj.text:
                    body = original_obj.text
                    # Handle RichTextValue objects
                    if hasattr(body, 'output'):
                        body = body.output
                    elif hasattr(body, 'raw'):
                        body = body.raw
                    # Strip HTML tags if present
                    if isinstance(body, str) and ('<' in body or '>' in body):
                        from html.parser import HTMLParser

                        class HTMLStripper(HTMLParser):
                            def __init__(self):
                                super().__init__()
                                self.text_parts = []

                            def handle_data(self, data):
                                self.text_parts.append(data)

                            def get_data(self):
                                return ' '.join(self.text_parts)

                        try:
                            stripper = HTMLStripper()
                            stripper.feed(body)
                            body = stripper.get_data()
                        except Exception:  # NOQA W0703
                            pass

                    if body:
                        parts.append(str(body))

                text = ' '.join(parts) if parts else None
            else:
                # For other indexes, use standard extraction
                text = getattr(obj, attr, None)

                # If getattr returned None, try to find an IIndexer adapter
                if text is None:
                    from zope.component import queryMultiAdapter
                    from plone.indexer.interfaces import IIndexer
                    from plone import api

                    catalog = api.portal.get_tool("portal_catalog")
                    indexer = queryMultiAdapter((obj, catalog), IIndexer, name=attr)
                    if indexer:
                        text = indexer()

            if text is None:
                continue

            if safe_callable(text):
                text = text()

            if text is None:
                continue

            # Handle RichTextValue objects (from plone.app.textfield)
            if hasattr(text, 'output'):
                text = text.output
            elif hasattr(text, 'raw'):
                text = text.raw

            # Strip HTML tags if present
            if isinstance(text, str) and ('<' in text or '>' in text):
                from html.parser import HTMLParser

                class HTMLStripper(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text_parts = []

                    def handle_data(self, data):
                        self.text_parts.append(data)

                    def get_data(self):
                        return ' '.join(self.text_parts)

                try:
                    stripper = HTMLStripper()
                    stripper.feed(text)
                    text = stripper.get_data()
                except Exception:  # NOQA W0703
                    # If HTML parsing fails, use text as-is
                    pass

            if text:
                if isinstance(text, (list, tuple)):
                    all_texts.extend(text)
                else:
                    all_texts.append(str(text))

        # Check that we're sending only strings and filter empty strings
        all_texts = [t for t in all_texts if isinstance(t, str) and t.strip()]
        if all_texts:
            return "\n".join(all_texts)
        return None

    def get_typesense_filter(self, name, value):
        """Convert text field query to Typesense filter for exact matching.

        Title and SearchableText should always use text search (get_typesense_query).
        Other text fields can use exact match filters.

        Note: ALL string values are wrapped in backticks as per Typesense filter syntax.
        """
        value = self._normalize_query(value)

        # Title and SearchableText should always use text search, never exact match
        # This is because they have infix: true in the schema and are optimized for search
        if name in ('SearchableText', 'Title', 'Description'):
            return None  # Will fall through to get_typesense_query()

        # Other text fields: if no wildcards, use exact match
        if value and '*' not in value:
            # Wrap in backticks (Typesense filter syntax requirement)
            return f"{name}:=`{value}`"
        return None

    def get_typesense_query(self, name, value):
        """Convert text search to Typesense query parameters.

        Returns dict with 'q' (search text) and 'query_by' (fields to search).
        Used for full-text search.
        """
        value = self._normalize_query(value)

        # For SearchableText, use the value as-is (it's a search term, not a filter)
        # For other fields with wildcards, strip them
        if name == "SearchableText":
            clean_value = value if value else ""
        else:
            # Strip wildcards - Typesense handles fuzzy/infix matching via schema
            clean_value = value.strip("*") if value else ""

        if not clean_value:
            return None

        # Build query_by list - search in the requested field
        query_by_fields = [name]

        # For SearchableText, also search Title with higher weight
        if name == "SearchableText":
            # query_by_fields = ["Title", "SearchableText"]
            query_by_fields = ["SearchableText"]

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
          is_folderish={'query': True} -> 'is_folderish:=true'
        """
        # Normalize query - extract 'query' from dict if present
        value = self._normalize_query(value)

        bool_val = 'true' if value else 'false'
        return f"{name}:={bool_val}"


class TUUIDIndex(BaseIndex):
    def get_typesense_filter(self, name, value):
        """Convert UUID query to Typesense filter.

        Examples:
          UID='abc123' -> 'UID:=abc123'
          UID={'query': 'abc123'} -> 'UID:=abc123'
        """
        # Normalize query - extract 'query' from dict if present
        value = self._normalize_query(value)

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
          path='/folder' -> 'path:=`/folder*`'
          path={'query': '/folder', 'depth': 0} -> 'path:=`/folder`'
          path={'query': '/folder', 'depth': 1} -> 'path:=`/folder*`'
          path={'query': ['/a', '/b']} -> 'path:=`/a*` || path:=`/b*`'

        Note: ALL string values are wrapped in backticks as per Typesense filter syntax.
        Note: depth filtering is ignored since Typesense doesn't have a depth field.
              The path prefix matching provides sufficient filtering.
        """
        if isinstance(value, str):
            # Parse string representation of list if needed
            parsed = _parse_value(value)
            if isinstance(parsed, list):
                paths = parsed
                depth = -1
            else:
                paths = [parsed]
                depth = -1
        else:
            depth = value.get("depth", -1)
            paths = value.get("query")
            # Parse string representation if needed
            paths = _parse_value(paths)
            if isinstance(paths, str):
                paths = [paths]

        if not paths:
            return None

        # Build filter for each path
        path_filters = []
        for path in paths:
            if depth == 0:
                # Exact path match - wrap in backticks
                path_filters.append(f"path:=`{path}`")
            else:
                # All descendants (depth ignored for Typesense) - wrap in backticks
                # Use wildcard to match all paths starting with this prefix
                path_filters.append(f"path:=`{path}*`")

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



