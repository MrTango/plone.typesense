# -*- coding: utf-8 -*-
"""Integration tests for query assembly and filter generation."""
import unittest
from unittest.mock import patch
from plone.typesense.query import QueryAssembler
from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex


class MockCatalog:
    """Mock catalog for testing."""
    def __init__(self):
        self._catalog = self
        self._indexes = {
            'portal_type': KeywordIndex('portal_type'),
            'review_state': KeywordIndex('review_state'),
        }
        self.indexes = self._indexes  # For keys() access

    def getIndex(self, name):
        """Return index by name."""
        return self._indexes.get(name)


class MockManager:
    """Mock manager for testing."""
    def __init__(self):
        self.catalog = MockCatalog()


class TestQueryAssemblyFilters(unittest.TestCase):
    """Test that QueryAssembler correctly assembles filters from various query formats."""

    def setUp(self):
        """Set up test fixture."""
        self.manager = MockManager()
        self.assembler = QueryAssembler(None, self.manager)
        # Mock get_ts_only_indexes to avoid registry lookup
        self.patcher = patch('plone.typesense.query.get_ts_only_indexes', return_value=[])
        self.patcher.start()

    def tearDown(self):
        """Tear down test fixture."""
        self.patcher.stop()

    def test_single_portal_type(self):
        """Test query with single portal_type value."""
        query = {'portal_type': 'Document'}
        params = self.assembler(query)
        self.assertIn('filter_by', params)
        self.assertEqual(params['filter_by'], 'portal_type:=`Document`')

    def test_multiple_portal_types_list(self):
        """Test query with multiple portal_type values as list."""
        query = {'portal_type': ['Document', 'Folder', 'Link']}
        params = self.assembler(query)
        self.assertIn('filter_by', params)
        # Check that it's NOT the wrong format
        self.assertNotIn("['Document'", params['filter_by'])
        # Check that it IS the correct format
        self.assertEqual(params['filter_by'], 'portal_type:[`Document`, `Folder`, `Link`]')

    def test_multiple_portal_types_with_spaces(self):
        """Test query with portal_type values containing spaces."""
        query = {'portal_type': ['Document', 'News Item', 'Collection']}
        params = self.assembler(query)
        self.assertIn('filter_by', params)
        # Check that spaces are properly escaped with backticks
        self.assertEqual(params['filter_by'], 'portal_type:[`Document`, `News Item`, `Collection`]')

    def test_dict_query_format(self):
        """Test query with dict format (Plone's extended query format)."""
        query = {
            'portal_type': {
                'query': ['Document', 'News Item', 'Folder'],
                'operator': 'or'
            }
        }
        params = self.assembler(query)
        self.assertIn('filter_by', params)
        self.assertEqual(params['filter_by'], 'portal_type:[`Document`, `News Item`, `Folder`]')

    def test_multiple_filters(self):
        """Test query with multiple filter fields."""
        query = {
            'portal_type': ['Document', 'Folder'],
            'review_state': 'published'
        }
        params = self.assembler(query)
        self.assertIn('filter_by', params)
        # Should contain both filters joined with &&
        self.assertIn('portal_type:[`Document`, `Folder`]', params['filter_by'])
        self.assertIn('review_state:=`published`', params['filter_by'])
        self.assertIn(' && ', params['filter_by'])


if __name__ == '__main__':
    unittest.main()
