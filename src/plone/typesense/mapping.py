"""MappingAdapter - auto-generate Typesense schema from Plone catalog indexes.

Maps Plone catalog index types to Typesense field types and generates
a complete Typesense collection schema from the current catalog state.
"""

from Acquisition import aq_base
from plone.folder.nogopip import GopipIndex
from Products.ExtendedPathIndex.ExtendedPathIndex import ExtendedPathIndex
from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex
from Products.PluginIndexes.DateIndex.DateIndex import DateIndex
from Products.PluginIndexes.DateRangeIndex.DateRangeIndex import DateRangeIndex
from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex
from Products.PluginIndexes.UUIDIndex.UUIDIndex import UUIDIndex
from Products.ZCTextIndex.ZCTextIndex import ZCTextIndex
from zope.component import getAdapters
from zope.interface import implementer

from plone.typesense import log
from plone.typesense.interfaces import IMappingAdapter, IMappingProvider


# Mapping of Plone catalog index types to Typesense field definitions.
# Each entry maps an index class to a callable that returns
# a dict with Typesense field properties.
CATALOG_TO_TYPESENSE_TYPE = {
    FieldIndex: lambda name: {"name": name, "type": "string", "optional": True},
    KeywordIndex: lambda name: {"name": name, "type": "string[]", "optional": True},
    ZCTextIndex: lambda name: {"name": name, "type": "string", "optional": True},
    BooleanIndex: lambda name: {"name": name, "type": "bool", "optional": True},
    DateIndex: lambda name: {"name": name, "type": "int64", "optional": True},
    UUIDIndex: lambda name: {"name": name, "type": "string", "optional": True},
    ExtendedPathIndex: lambda name: {"name": name, "type": "string", "optional": True},
    GopipIndex: lambda name: {
        "name": name,
        "type": "int32",
        "optional": True,
        "sort": True,
    },
}

try:
    from Products.DateRecurringIndex.index import DateRecurringIndex

    CATALOG_TO_TYPESENSE_TYPE[DateRecurringIndex] = lambda name: {
        "name": name,
        "type": "int64",
        "optional": True,
    }
except ImportError:
    pass

# Well-known Plone fields that need specific Typesense configurations
# beyond the default auto-mapping.
FIELD_OVERRIDES = {
    "id": {"name": "plone_id", "type": "string", "optional": True},
    "Title": {"name": "Title", "type": "string", "infix": True, "optional": True},
    "Description": {"name": "Description", "type": "string", "optional": True},
    "SearchableText": {
        "name": "SearchableText",
        "type": "string",
        "infix": True,
        "optional": True,
    },
    "sortable_title": {
        "name": "sortable_title",
        "type": "string",
        "sort": True,
        "optional": True,
    },
    "portal_type": {
        "name": "portal_type",
        "type": "string",
        "facet": True,
        "optional": True,
    },
    "Type": {"name": "Type", "type": "string", "facet": True, "optional": True},
    "review_state": {
        "name": "review_state",
        "type": "string",
        "facet": True,
        "optional": True,
    },
    "Subject": {
        "name": "Subject",
        "type": "string[]",
        "facet": True,
        "optional": True,
    },
    "allowedRolesAndUsers": {
        "name": "allowedRolesAndUsers",
        "type": "string[]",
        "facet": False,
        "optional": True,
    },
    "language": {
        "name": "language",
        "type": "string",
        "facet": True,
        "optional": True,
    },
    "path": {"name": "path", "type": "string", "sort": True, "optional": True},
    "Date": {"name": "Date", "type": "int64", "facet": False, "optional": True},
    "created": {"name": "created", "type": "int64", "facet": False, "optional": True},
    "modified": {"name": "modified", "type": "int64", "facet": False, "optional": True},
    "effective": {
        "name": "effective",
        "type": "int64",
        "facet": False,
        "optional": True,
    },
    "expires": {"name": "expires", "type": "int64", "facet": False, "optional": True},
    "total_comments": {
        "name": "total_comments",
        "type": "int32",
        "facet": False,
        "optional": True,
    },
    "getObjPositionInParent": {
        "name": "getObjPositionInParent",
        "type": "string",
        "sort": True,
        "optional": True,
    },
    "cmf_uid": {"name": "cmf_uid", "index": False, "optional": True, "type": "auto"},
}


def get_typesense_field_for_index(index_name, index_obj):
    """Convert a single Plone catalog index to a Typesense field definition.

    :param index_name: The name of the catalog index
    :param index_obj: The actual catalog index object
    :returns: A dict with Typesense field properties, or None if unmappable
    """
    # Check overrides first
    if index_name in FIELD_OVERRIDES:
        return FIELD_OVERRIDES[index_name].copy()

    # Use __class__ for compatibility with Acquisition-wrapped objects
    # and test mocks. aq_base strips the wrapper but __class__ gives
    # the real class in both cases.
    unwrapped = aq_base(index_obj)
    index_type = unwrapped.__class__

    # DateRangeIndex produces two int64 fields
    if index_type is DateRangeIndex:
        return [
            {
                "name": f"{index_name}_start",
                "type": "int64",
                "optional": True,
            },
            {
                "name": f"{index_name}_end",
                "type": "int64",
                "optional": True,
            },
        ]

    mapper = CATALOG_TO_TYPESENSE_TYPE.get(index_type)
    if mapper is not None:
        return mapper(index_name)

    log.warning(
        "No Typesense mapping for catalog index '%s' of type '%s'. "
        "Skipping.",
        index_name,
        index_type.__name__,
    )
    return None


@implementer(IMappingAdapter)
class MappingAdapter:
    """Generates a Typesense collection schema from Plone catalog indexes.

    Iterates over all indexes in the portal_catalog, maps each to
    the appropriate Typesense field type, and produces a complete
    collection schema dict suitable for passing to the Typesense
    collections.create() API.
    """

    def __init__(self, catalog):
        self.catalog = catalog

    def get_schema(self, collection_name=None):
        """Generate a full Typesense collection schema.

        :param collection_name: Name of the Typesense collection.
            If None, will be set later by the caller.
        :returns: dict suitable for typesense.collections.create()
        """
        fields = self._build_fields()
        schema = {
            "name": collection_name or "",
            "fields": fields,
            "token_separators": ["-"],
        }
        return schema

    def _build_fields(self):
        """Build the list of Typesense field definitions from catalog indexes.

        Also queries registered IMappingProvider adapters for additional
        field contributions.
        """
        fields = []
        seen_names = set()
        catalog = getattr(self.catalog, "_catalog", self.catalog)

        for index_name in catalog.indexes():
            try:
                index_obj = catalog.getIndex(index_name)
            except KeyError:
                continue

            field_def = get_typesense_field_for_index(index_name, index_obj)
            if field_def is None:
                continue

            if isinstance(field_def, list):
                # DateRangeIndex produces multiple fields
                for fd in field_def:
                    if fd["name"] not in seen_names:
                        fields.append(fd)
                        seen_names.add(fd["name"])
            else:
                if field_def["name"] not in seen_names:
                    fields.append(field_def)
                    seen_names.add(field_def["name"])

        # Query IMappingProvider adapters for extra fields
        try:
            providers = getAdapters((self.catalog,), IMappingProvider)
            for name, provider in providers:
                extra_fields = provider.get_fields()
                for fd in extra_fields:
                    if fd.get("name") and fd["name"] not in seen_names:
                        fields.append(fd)
                        seen_names.add(fd["name"])
        except Exception:
            # If component architecture is not available (e.g., in tests),
            # just skip provider lookup
            pass

        return fields

    def get_field_names(self):
        """Return a set of field names that would be in the schema."""
        fields = self._build_fields()
        return {f["name"] for f in fields}


def convert_catalog_to_typesense(catalog, collection_name=None):
    """Convenience function to generate a Typesense schema from catalog state.

    :param catalog: The Plone portal_catalog tool
    :param collection_name: Optional collection name
    :returns: dict suitable for typesense.collections.create()
    """
    adapter = MappingAdapter(catalog)
    return adapter.get_schema(collection_name=collection_name)


def detect_schema_changes(catalog, current_schema):
    """Compare catalog indexes against a current Typesense schema.

    Detects:
    - New indexes in the catalog not in Typesense
    - Indexes removed from the catalog but still in Typesense
    - Type mismatches between catalog index type and Typesense field type

    :param catalog: The Plone portal_catalog tool
    :param current_schema: The current Typesense collection schema dict
        (as returned by collection.retrieve())
    :returns: dict with keys 'added', 'removed', 'type_changed', each
        containing relevant field info
    """
    adapter = MappingAdapter(catalog)
    proposed_fields = adapter._build_fields()

    # Build lookup dicts
    proposed_by_name = {}
    for f in proposed_fields:
        proposed_by_name[f["name"]] = f

    current_fields = current_schema.get("fields", [])
    current_by_name = {}
    for f in current_fields:
        current_by_name[f["name"]] = f

    # Ignore auto-schema wildcard fields
    current_by_name.pop(".*", None)

    proposed_names = set(proposed_by_name.keys())
    current_names = set(current_by_name.keys())

    added = []
    for name in sorted(proposed_names - current_names):
        added.append(proposed_by_name[name])

    removed = []
    for name in sorted(current_names - proposed_names):
        removed.append(current_by_name[name])

    type_changed = []
    for name in sorted(proposed_names & current_names):
        proposed_type = proposed_by_name[name].get("type")
        current_type = current_by_name[name].get("type")
        if proposed_type and current_type and proposed_type != current_type:
            type_changed.append(
                {
                    "name": name,
                    "catalog_type": proposed_type,
                    "typesense_type": current_type,
                }
            )

    return {
        "added": added,
        "removed": removed,
        "type_changed": type_changed,
    }
