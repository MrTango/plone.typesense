from dataclasses import dataclass
from Products.CMFCore.interfaces import IIndexQueueProcessor
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.interface import Attribute, Interface



class ITypesenseManager(Interface):
    """Marker interface for the Typesense search manager."""


# Alias used by manager.py for registry lookups.
# The actual schema is ITypesenseControlpanel in the controlpanels package.
try:
    from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
        ITypesenseControlpanel as ITypesenseSettings,
    )
except ImportError:
    ITypesenseSettings = Interface


class IQueryAssembler(Interface):
    """Assembles Plone catalog queries into Typesense search parameters."""

    def normalize(query):
        """Normalize query parameters (extract sort_on, etc.).

        Returns (normalized_query, sort_list)
        """

    def __call__(query):
        """Build Typesense search parameters from Plone query dict.

        Returns dict with 'q', 'query_by', 'filter_by', 'sort_by', etc.
        """


class IPloneTypesenseLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class ITypesenseSearchIndexQueueProcessor(IIndexQueueProcessor):
    """Index queue processor for Typesense."""


class IReindexActive(Interface):
    """Marker interface applied to the request during bulk reindex.

    When this marker is active, the IndexProcessor knows a full rebuild
    is in progress and indexes all attributes for every object.
    """


class IAdditionalIndexDataProvider(Interface):
    """Adapter interface for injecting extra data into the Typesense document.

    Register named adapters for (content_object,) that provide this interface.
    Each adapter's __call__ receives (catalog, index_data) and returns the
    updated index_data dict.
    """

    def __call__(catalog, index_data):
        """Return updated index_data dict with additional fields."""


class IMappingAdapter(Interface):
    """Adapter that generates a Typesense collection schema from a Plone catalog.

    Given a portal_catalog, this adapter introspects the registered indexes
    and produces a Typesense-compatible schema dict.
    """

    catalog = Attribute("The portal_catalog being adapted")

    def get_schema(collection_name=None):
        """Return a complete Typesense collection schema dict.

        :param collection_name: Optional name for the collection
        :returns: dict suitable for typesense.collections.create()
        """

    def get_field_names():
        """Return a set of field names that would be in the schema."""


class IMappingProvider(Interface):
    """Extension point: allows external packages to contribute extra fields
    to the Typesense schema.

    Register named adapters for (catalog,) -> IMappingProvider to add
    custom fields beyond those auto-detected from catalog indexes.
    """

    def get_fields():
        """Return a list of Typesense field definition dicts.

        Each dict should have at minimum 'name' and 'type' keys.
        Example::

            [
                {"name": "my_custom_field", "type": "string", "facet": True},
            ]
        """


@dataclass
class IndexingActions:

    index: dict[str, dict]
    reindex: dict[str, dict]
    unindex: dict[str, dict]
    index_blobs: dict[str, dict]
    uuid_path: dict[str, str]

    def __len__(self):
        size = 0
        size += len(self.index)
        size += len(self.reindex)
        size += len(self.unindex)
        return size

    def all(self) -> list[tuple[str, str, dict]]:
        all_data = []
        for attr, action in (
            ("index", "index"),
            ("reindex", "update"),
            ("unindex", "delete"),
        ):
            action_data = [
                (uuid, data) for uuid, data in getattr(self, attr, {}).items()
            ]
            if action_data:
                all_data.extend([(action, uuid, data) for uuid, data in action_data])
        return all_data
