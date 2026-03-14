"""Tests for plone.typesense.mapping — auto-generating Typesense schemas
from Plone catalog indexes."""

import unittest
from unittest.mock import MagicMock, patch


class TestGetTypesenseFieldForIndex(unittest.TestCase):
    """Unit tests for get_typesense_field_for_index()."""

    def _call(self, index_name, index_obj):
        from plone.typesense.mapping import get_typesense_field_for_index

        return get_typesense_field_for_index(index_name, index_obj)

    def _make_index(self, klass):
        """Create a mock index that looks like the given class."""
        mock = MagicMock(spec=klass)
        mock.__class__ = klass
        return mock

    def test_field_index(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        result = self._call("my_field", self._make_index(FieldIndex))
        self.assertEqual(result["name"], "my_field")
        self.assertEqual(result["type"], "string")
        self.assertTrue(result["optional"])

    def test_keyword_index(self):
        from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex

        result = self._call("my_keywords", self._make_index(KeywordIndex))
        self.assertEqual(result["name"], "my_keywords")
        self.assertEqual(result["type"], "string[]")

    def test_boolean_index(self):
        from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex

        result = self._call("is_active", self._make_index(BooleanIndex))
        self.assertEqual(result["name"], "is_active")
        self.assertEqual(result["type"], "bool")

    def test_date_index(self):
        from Products.PluginIndexes.DateIndex.DateIndex import DateIndex

        result = self._call("created", self._make_index(DateIndex))
        self.assertEqual(result["name"], "created")
        self.assertEqual(result["type"], "int64")

    def test_zctextindex(self):
        from Products.ZCTextIndex.ZCTextIndex import ZCTextIndex

        result = self._call("my_text", self._make_index(ZCTextIndex))
        self.assertEqual(result["name"], "my_text")
        self.assertEqual(result["type"], "string")

    def test_uuid_index(self):
        from Products.PluginIndexes.UUIDIndex.UUIDIndex import UUIDIndex

        result = self._call("UID", self._make_index(UUIDIndex))
        self.assertEqual(result["name"], "UID")
        self.assertEqual(result["type"], "string")

    def test_extended_path_index(self):
        from Products.ExtendedPathIndex.ExtendedPathIndex import ExtendedPathIndex

        result = self._call("path", self._make_index(ExtendedPathIndex))
        # path has an override
        self.assertEqual(result["name"], "path")
        self.assertEqual(result["type"], "string")
        self.assertTrue(result.get("sort"))

    def test_gopip_index(self):
        from plone.folder.nogopip import GopipIndex

        result = self._call("getObjPositionInParent", self._make_index(GopipIndex))
        # Has override
        self.assertEqual(result["name"], "getObjPositionInParent")

    def test_date_range_index(self):
        from Products.PluginIndexes.DateRangeIndex.DateRangeIndex import DateRangeIndex

        result = self._call("effectiveRange", self._make_index(DateRangeIndex))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "effectiveRange_start")
        self.assertEqual(result[0]["type"], "int64")
        self.assertEqual(result[1]["name"], "effectiveRange_end")
        self.assertEqual(result[1]["type"], "int64")

    def test_override_title(self):
        from Products.ZCTextIndex.ZCTextIndex import ZCTextIndex

        result = self._call("Title", self._make_index(ZCTextIndex))
        self.assertEqual(result["name"], "Title")
        self.assertEqual(result["type"], "string")
        self.assertTrue(result.get("infix"))

    def test_override_searchabletext(self):
        from Products.ZCTextIndex.ZCTextIndex import ZCTextIndex

        result = self._call("SearchableText", self._make_index(ZCTextIndex))
        self.assertEqual(result["name"], "SearchableText")
        self.assertTrue(result.get("infix"))

    def test_override_portal_type(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        result = self._call("portal_type", self._make_index(FieldIndex))
        self.assertTrue(result.get("facet"))

    def test_override_subject(self):
        from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex

        result = self._call("Subject", self._make_index(KeywordIndex))
        self.assertEqual(result["type"], "string[]")
        self.assertTrue(result.get("facet"))

    def test_override_review_state(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        result = self._call("review_state", self._make_index(FieldIndex))
        self.assertTrue(result.get("facet"))

    def test_unknown_index_type_returns_none(self):
        class UnknownIndex:
            pass

        mock = MagicMock(spec=UnknownIndex)
        mock.__class__ = UnknownIndex
        result = self._call("weird_index", mock)
        self.assertIsNone(result)


class TestMappingAdapterUnit(unittest.TestCase):
    """Unit tests for MappingAdapter using mock catalogs."""

    def _make_adapter(self, indexes_dict):
        """Create a MappingAdapter with a mock catalog.

        :param indexes_dict: dict mapping index_name to index class
        """
        from plone.typesense.mapping import MappingAdapter

        mock_catalog = MagicMock()
        mock_internal = MagicMock()
        mock_catalog._catalog = mock_internal
        mock_internal.indexes.return_value = list(indexes_dict.keys())

        def get_index(name):
            klass = indexes_dict[name]
            mock_idx = MagicMock(spec=klass)
            mock_idx.__class__ = klass
            return mock_idx

        mock_internal.getIndex.side_effect = get_index
        return MappingAdapter(mock_catalog)

    def test_get_schema_returns_dict(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        adapter = self._make_adapter({"my_field": FieldIndex})
        schema = adapter.get_schema(collection_name="test_collection")

        self.assertIsInstance(schema, dict)
        self.assertEqual(schema["name"], "test_collection")
        self.assertIn("fields", schema)
        self.assertIn("token_separators", schema)

    def test_get_schema_includes_field_index(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        adapter = self._make_adapter({"custom_field": FieldIndex})
        schema = adapter.get_schema()
        field_names = {f["name"] for f in schema["fields"]}
        self.assertIn("custom_field", field_names)

    def test_get_schema_includes_keyword_index(self):
        from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex

        adapter = self._make_adapter({"tags": KeywordIndex})
        schema = adapter.get_schema()
        fields_by_name = {f["name"]: f for f in schema["fields"]}
        self.assertIn("tags", fields_by_name)
        self.assertEqual(fields_by_name["tags"]["type"], "string[]")

    def test_get_schema_date_range_produces_two_fields(self):
        from Products.PluginIndexes.DateRangeIndex.DateRangeIndex import DateRangeIndex

        adapter = self._make_adapter({"effectiveRange": DateRangeIndex})
        schema = adapter.get_schema()
        field_names = {f["name"] for f in schema["fields"]}
        self.assertIn("effectiveRange_start", field_names)
        self.assertIn("effectiveRange_end", field_names)

    def test_get_schema_no_duplicates(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        adapter = self._make_adapter({"portal_type": FieldIndex})
        schema = adapter.get_schema()
        names = [f["name"] for f in schema["fields"]]
        self.assertEqual(len(names), len(set(names)))

    def test_get_field_names(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
        from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex

        adapter = self._make_adapter({
            "my_field": FieldIndex,
            "is_active": BooleanIndex,
        })
        names = adapter.get_field_names()
        self.assertIn("my_field", names)
        self.assertIn("is_active", names)

    def test_get_schema_default_collection_name(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        adapter = self._make_adapter({"x": FieldIndex})
        schema = adapter.get_schema()
        self.assertEqual(schema["name"], "")

    def test_multiple_index_types(self):
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
        from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex
        from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex
        from Products.PluginIndexes.DateIndex.DateIndex import DateIndex

        adapter = self._make_adapter({
            "title_field": FieldIndex,
            "keywords": KeywordIndex,
            "is_folderish": BooleanIndex,
            "created": DateIndex,
        })
        schema = adapter.get_schema(collection_name="multi")
        fields_by_name = {f["name"]: f for f in schema["fields"]}
        self.assertEqual(fields_by_name["title_field"]["type"], "string")
        self.assertEqual(fields_by_name["keywords"]["type"], "string[]")
        self.assertEqual(fields_by_name["is_folderish"]["type"], "bool")
        self.assertEqual(fields_by_name["created"]["type"], "int64")


class TestConvertCatalogToTypesense(unittest.TestCase):
    """Unit tests for the convert_catalog_to_typesense convenience function."""

    def test_returns_schema_dict(self):
        from plone.typesense.mapping import convert_catalog_to_typesense
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        mock_catalog = MagicMock()
        mock_internal = MagicMock()
        mock_catalog._catalog = mock_internal
        mock_internal.indexes.return_value = ["my_field"]

        mock_idx = MagicMock(spec=FieldIndex)
        mock_idx.__class__ = FieldIndex
        mock_internal.getIndex.return_value = mock_idx

        schema = convert_catalog_to_typesense(mock_catalog, "my_collection")
        self.assertEqual(schema["name"], "my_collection")
        self.assertIn("fields", schema)


class TestDetectSchemaChanges(unittest.TestCase):
    """Unit tests for detect_schema_changes()."""

    def _make_catalog_adapter(self, indexes_dict):
        mock_catalog = MagicMock()
        mock_internal = MagicMock()
        mock_catalog._catalog = mock_internal
        mock_internal.indexes.return_value = list(indexes_dict.keys())

        def get_index(name):
            klass = indexes_dict[name]
            mock_idx = MagicMock(spec=klass)
            mock_idx.__class__ = klass
            return mock_idx

        mock_internal.getIndex.side_effect = get_index
        return mock_catalog

    def test_no_changes(self):
        from plone.typesense.mapping import detect_schema_changes
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        catalog = self._make_catalog_adapter({"custom_field": FieldIndex})
        current_schema = {
            "fields": [
                {"name": "custom_field", "type": "string"},
            ]
        }
        diff = detect_schema_changes(catalog, current_schema)
        self.assertEqual(diff["added"], [])
        self.assertEqual(diff["removed"], [])
        self.assertEqual(diff["type_changed"], [])

    def test_added_field(self):
        from plone.typesense.mapping import detect_schema_changes
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
        from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex

        catalog = self._make_catalog_adapter({
            "existing": FieldIndex,
            "new_field": BooleanIndex,
        })
        current_schema = {
            "fields": [
                {"name": "existing", "type": "string"},
            ]
        }
        diff = detect_schema_changes(catalog, current_schema)
        added_names = [f["name"] for f in diff["added"]]
        self.assertIn("new_field", added_names)

    def test_removed_field(self):
        from plone.typesense.mapping import detect_schema_changes
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        catalog = self._make_catalog_adapter({"existing": FieldIndex})
        current_schema = {
            "fields": [
                {"name": "existing", "type": "string"},
                {"name": "old_field", "type": "string"},
            ]
        }
        diff = detect_schema_changes(catalog, current_schema)
        removed_names = [f["name"] for f in diff["removed"]]
        self.assertIn("old_field", removed_names)

    def test_type_mismatch(self):
        from plone.typesense.mapping import detect_schema_changes
        from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex

        catalog = self._make_catalog_adapter({"my_flag": BooleanIndex})
        current_schema = {
            "fields": [
                {"name": "my_flag", "type": "string"},  # should be bool
            ]
        }
        diff = detect_schema_changes(catalog, current_schema)
        self.assertEqual(len(diff["type_changed"]), 1)
        self.assertEqual(diff["type_changed"][0]["name"], "my_flag")
        self.assertEqual(diff["type_changed"][0]["catalog_type"], "bool")
        self.assertEqual(diff["type_changed"][0]["typesense_type"], "string")

    def test_ignores_wildcard_field(self):
        from plone.typesense.mapping import detect_schema_changes
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex

        catalog = self._make_catalog_adapter({"my_field": FieldIndex})
        current_schema = {
            "fields": [
                {"name": ".*", "type": "auto"},
                {"name": "my_field", "type": "string"},
            ]
        }
        diff = detect_schema_changes(catalog, current_schema)
        # The wildcard should not appear as "removed"
        removed_names = [f["name"] for f in diff["removed"]]
        self.assertNotIn(".*", removed_names)


class TestMappingAdapterRealisticCatalog(unittest.TestCase):
    """Tests using a realistic mock catalog with common Plone index types."""

    def setUp(self):
        """Set up a mock catalog that mimics a real Plone catalog."""
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
        from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex
        from Products.PluginIndexes.DateIndex.DateIndex import DateIndex
        from Products.PluginIndexes.BooleanIndex.BooleanIndex import BooleanIndex
        from Products.PluginIndexes.UUIDIndex.UUIDIndex import UUIDIndex
        from Products.ExtendedPathIndex.ExtendedPathIndex import ExtendedPathIndex
        from Products.ZCTextIndex.ZCTextIndex import ZCTextIndex
        from Products.PluginIndexes.DateRangeIndex.DateRangeIndex import DateRangeIndex

        self.index_types = {
            "Title": ZCTextIndex,
            "Description": ZCTextIndex,
            "SearchableText": ZCTextIndex,
            "portal_type": FieldIndex,
            "review_state": FieldIndex,
            "Subject": KeywordIndex,
            "created": DateIndex,
            "modified": DateIndex,
            "effective": DateIndex,
            "expires": DateIndex,
            "Date": DateIndex,
            "allowedRolesAndUsers": KeywordIndex,
            "UID": UUIDIndex,
            "path": ExtendedPathIndex,
            "is_folderish": BooleanIndex,
            "effectiveRange": DateRangeIndex,
            "sortable_title": FieldIndex,
            "language": FieldIndex,
            "Type": FieldIndex,
        }

        mock_catalog = MagicMock()
        mock_internal = MagicMock()
        mock_catalog._catalog = mock_internal
        mock_internal.indexes.return_value = list(self.index_types.keys())

        def get_index(name):
            klass = self.index_types[name]
            mock_idx = MagicMock(spec=klass)
            mock_idx.__class__ = klass
            return mock_idx

        mock_internal.getIndex.side_effect = get_index
        self.catalog = mock_catalog

    def test_adapter_produces_schema(self):
        from plone.typesense.mapping import MappingAdapter

        adapter = MappingAdapter(self.catalog)
        schema = adapter.get_schema(collection_name="test")
        self.assertEqual(schema["name"], "test")
        self.assertGreater(len(schema["fields"]), 0)

    def test_expected_fields_present(self):
        from plone.typesense.mapping import MappingAdapter

        adapter = MappingAdapter(self.catalog)
        names = adapter.get_field_names()
        for expected in ("Title", "portal_type", "review_state", "path"):
            self.assertIn(expected, names, f"Expected '{expected}' in field names")

    def test_convert_catalog_to_typesense(self):
        from plone.typesense.mapping import convert_catalog_to_typesense

        schema = convert_catalog_to_typesense(self.catalog, "integration_test")
        self.assertEqual(schema["name"], "integration_test")
        field_names = {f["name"] for f in schema["fields"]}
        self.assertIn("Title", field_names)
        self.assertIn("SearchableText", field_names)

    def test_schema_fields_have_required_keys(self):
        from plone.typesense.mapping import MappingAdapter

        adapter = MappingAdapter(self.catalog)
        schema = adapter.get_schema()
        for field in schema["fields"]:
            self.assertIn("name", field, f"Field missing 'name': {field}")
            self.assertIn("type", field, f"Field {field['name']} missing 'type'")

    def test_detect_schema_changes_with_empty_typesense(self):
        from plone.typesense.mapping import detect_schema_changes

        diff = detect_schema_changes(self.catalog, {"fields": []})
        self.assertGreater(len(diff["added"]), 0)
        self.assertEqual(len(diff["removed"]), 0)

    def test_date_range_index_splits_into_two_fields(self):
        from plone.typesense.mapping import MappingAdapter

        adapter = MappingAdapter(self.catalog)
        names = adapter.get_field_names()
        self.assertIn("effectiveRange_start", names)
        self.assertIn("effectiveRange_end", names)

    def test_field_type_consistency(self):
        """Verify that known overrides produce the correct types."""
        from plone.typesense.mapping import MappingAdapter

        adapter = MappingAdapter(self.catalog)
        schema = adapter.get_schema()
        fields_by_name = {f["name"]: f for f in schema["fields"]}

        self.assertEqual(fields_by_name["Title"]["type"], "string")
        self.assertTrue(fields_by_name["Title"].get("infix"))
        self.assertEqual(fields_by_name["Subject"]["type"], "string[]")
        self.assertTrue(fields_by_name["Subject"].get("facet"))
        self.assertEqual(fields_by_name["portal_type"]["type"], "string")
        self.assertTrue(fields_by_name["portal_type"].get("facet"))
        self.assertEqual(fields_by_name["created"]["type"], "int64")
        self.assertEqual(fields_by_name["is_folderish"]["type"], "bool")


class TestIMappingProviderIntegration(unittest.TestCase):
    """Test that IMappingProvider adapters are picked up."""

    def test_provider_fields_included(self):
        from plone.typesense.mapping import MappingAdapter
        from plone.typesense.interfaces import IMappingProvider
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
        from zope.interface import implementer

        @implementer(IMappingProvider)
        class CustomProvider:
            def __init__(self, catalog):
                self.catalog = catalog

            def get_fields(self):
                return [
                    {"name": "custom_rating", "type": "float", "optional": True},
                ]

        mock_catalog = MagicMock()
        mock_internal = MagicMock()
        mock_catalog._catalog = mock_internal
        mock_internal.indexes.return_value = ["simple"]

        mock_idx = MagicMock(spec=FieldIndex)
        mock_idx.__class__ = FieldIndex
        mock_internal.getIndex.return_value = mock_idx

        with patch(
            "plone.typesense.mapping.getAdapters",
            return_value=[("custom", CustomProvider(mock_catalog))],
        ):
            adapter = MappingAdapter(mock_catalog)
            schema = adapter.get_schema()
            field_names = {f["name"] for f in schema["fields"]}
            self.assertIn("custom_rating", field_names)
            self.assertIn("simple", field_names)

    def test_provider_does_not_duplicate_fields(self):
        from plone.typesense.mapping import MappingAdapter
        from plone.typesense.interfaces import IMappingProvider
        from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
        from zope.interface import implementer

        @implementer(IMappingProvider)
        class DuplicatingProvider:
            def __init__(self, catalog):
                self.catalog = catalog

            def get_fields(self):
                return [
                    {"name": "simple", "type": "int32"},  # same name as catalog index
                ]

        mock_catalog = MagicMock()
        mock_internal = MagicMock()
        mock_catalog._catalog = mock_internal
        mock_internal.indexes.return_value = ["simple"]

        mock_idx = MagicMock(spec=FieldIndex)
        mock_idx.__class__ = FieldIndex
        mock_internal.getIndex.return_value = mock_idx

        with patch(
            "plone.typesense.mapping.getAdapters",
            return_value=[("dup", DuplicatingProvider(mock_catalog))],
        ):
            adapter = MappingAdapter(mock_catalog)
            schema = adapter.get_schema()
            # "simple" should appear only once (catalog takes precedence)
            names = [f["name"] for f in schema["fields"]]
            self.assertEqual(names.count("simple"), 1)


class TestInterfacesExist(unittest.TestCase):
    """Verify that the new interfaces are properly defined."""

    def test_imapping_adapter_interface(self):
        from plone.typesense.interfaces import IMappingAdapter

        # zope.interface methods are in the interface's namesAndDescriptions
        method_names = [name for name, _ in IMappingAdapter.namesAndDescriptions()]
        self.assertIn("get_schema", method_names)
        self.assertIn("get_field_names", method_names)

    def test_imapping_provider_interface(self):
        from plone.typesense.interfaces import IMappingProvider

        method_names = [name for name, _ in IMappingProvider.namesAndDescriptions()]
        self.assertIn("get_fields", method_names)

    def test_mapping_adapter_implements_interface(self):
        from plone.typesense.interfaces import IMappingAdapter
        from plone.typesense.mapping import MappingAdapter

        self.assertTrue(IMappingAdapter.implementedBy(MappingAdapter))
