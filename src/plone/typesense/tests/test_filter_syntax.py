# -*- coding: utf-8 -*-
"""Unit tests for Typesense filter syntax generation."""
import unittest
from plone.typesense.indexes import TKeywordIndex, TFieldIndex


class MockCatalog:
    """Mock catalog for testing."""
    pass


class MockKeywordIndex:
    """Mock KeywordIndex for testing."""
    def __init__(self, index_id):
        self.id = index_id

    def getIndexSourceNames(self):
        return [self.id]


class TestKeywordIndexFilterSyntax(unittest.TestCase):
    """Test that TKeywordIndex generates correct Typesense filter syntax."""

    def setUp(self):
        """Set up test fixture."""
        self.catalog = MockCatalog()
        mock_index = MockKeywordIndex('portal_type')
        self.index = TKeywordIndex(self.catalog, mock_index)

    def test_single_value_simple(self):
        """Test single value without spaces."""
        result = self.index.get_typesense_filter('portal_type', 'Document')
        self.assertEqual(result, 'portal_type:=`Document`')

    def test_single_value_with_spaces(self):
        """Test single value with spaces."""
        result = self.index.get_typesense_filter('portal_type', 'News Item')
        self.assertEqual(result, 'portal_type:=`News Item`')

    def test_list_single_value(self):
        """Test list with single value."""
        result = self.index.get_typesense_filter('portal_type', ['Document'])
        self.assertEqual(result, 'portal_type:[`Document`]')

    def test_list_multiple_values_no_spaces(self):
        """Test list with multiple values without spaces."""
        result = self.index.get_typesense_filter('portal_type', ['Document', 'Folder', 'Link'])
        self.assertEqual(result, 'portal_type:[`Document`, `Folder`, `Link`]')

    def test_list_multiple_values_with_spaces(self):
        """Test list with multiple values, some with spaces."""
        result = self.index.get_typesense_filter('portal_type', ['Document', 'News Item', 'Collection'])
        self.assertEqual(result, 'portal_type:[`Document`, `News Item`, `Collection`]')

    def test_list_all_values_with_spaces(self):
        """Test list where all values have spaces."""
        result = self.index.get_typesense_filter('portal_type', ['News Item', 'Event Item'])
        self.assertEqual(result, 'portal_type:[`News Item`, `Event Item`]')

    def test_dict_query_with_list(self):
        """Test dict query format with list."""
        result = self.index.get_typesense_filter('portal_type', {
            'query': ['Document', 'News Item', 'Folder'],
            'operator': 'or'
        })
        self.assertEqual(result, 'portal_type:[`Document`, `News Item`, `Folder`]')

    def test_dict_query_with_single_value(self):
        """Test dict query format with single value."""
        result = self.index.get_typesense_filter('portal_type', {
            'query': 'Document'
        })
        self.assertEqual(result, 'portal_type:=`Document`')

    def test_tuple_values(self):
        """Test tuple instead of list."""
        result = self.index.get_typesense_filter('portal_type', ('Document', 'Folder'))
        self.assertEqual(result, 'portal_type:[`Document`, `Folder`]')

    def test_set_values(self):
        """Test set instead of list."""
        result = self.index.get_typesense_filter('portal_type', {'Document', 'Folder'})
        # Set order is undefined, so check both possibilities
        self.assertIn(result, [
            'portal_type:[`Document`, `Folder`]',
            'portal_type:[`Folder`, `Document`]'
        ])

    def test_string_representation_of_list(self):
        """Test string representation of a list is parsed and filtered correctly."""
        result = self.index.get_typesense_filter('portal_type', "['Document', 'Folder']")
        self.assertEqual(result, 'portal_type:[`Document`, `Folder`]')

    def test_string_representation_of_tuple(self):
        """Test string representation of a tuple is parsed and filtered correctly."""
        result = self.index.get_typesense_filter('portal_type', "('Document', 'News Item')")
        self.assertEqual(result, 'portal_type:[`Document`, `News Item`]')

    def test_string_representation_with_whitespace(self):
        """Test string representation with leading/trailing whitespace is parsed correctly."""
        result = self.index.get_typesense_filter('portal_type', " ['Document', 'Folder'] ")
        self.assertEqual(result, 'portal_type:[`Document`, `Folder`]')


if __name__ == '__main__':
    unittest.main()
