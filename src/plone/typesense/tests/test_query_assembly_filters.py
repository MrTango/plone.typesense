"""Integration tests for query assembly and filter generation."""
import unittest
from unittest.mock import patch
from plone.typesense.query import TypesenseQueryAssembler
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


class TestTypesenseQueryAssemblyFilters(unittest.TestCase):
    """Test that TypesenseQueryAssembler correctly assembles filters."""

    def setUp(self):
        """Set up test fixture."""
        self.manager = MockManager()
        self.assembler = TypesenseQueryAssembler(None, self.manager)
        # Mock get_ts_only_indexes to avoid registry lookup
        self.patcher = patch('plone.typesense.query.get_ts_only_indexes', return_value=set())
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
        self.assertEqual(params['filter_by'], 'portal_type:[`Document`, `Folder`, `Link`]')

    def test_multiple_portal_types_with_spaces(self):
        """Test query with portal_type values containing spaces."""
        query = {'portal_type': ['Document', 'News Item', 'Collection']}
        params = self.assembler(query)
        self.assertIn('filter_by', params)
        self.assertEqual(
            params['filter_by'],
            'portal_type:[`Document`, `News Item`, `Collection`]'
        )

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
        self.assertEqual(
            params['filter_by'],
            'portal_type:[`Document`, `News Item`, `Folder`]'
        )

    def test_multiple_filters(self):
        """Test query with multiple filter fields."""
        query = {
            'portal_type': ['Document', 'Folder'],
            'review_state': 'published'
        }
        params = self.assembler(query)
        self.assertIn('filter_by', params)
        self.assertIn('portal_type:[`Document`, `Folder`]', params['filter_by'])
        self.assertIn('review_state:=`published`', params['filter_by'])
        self.assertIn(' && ', params['filter_by'])

    def test_empty_query_returns_match_all(self):
        """Test empty query returns match-all."""
        params = self.assembler({})
        self.assertEqual(params['q'], '*')
        self.assertNotIn('filter_by', params)

    def test_unknown_index_ignored(self):
        """Test that unknown index names are skipped."""
        query = {'nonexistent_field': 'value'}
        params = self.assembler(query)
        self.assertEqual(params['q'], '*')
        self.assertNotIn('filter_by', params)

    def test_normalize_extracts_sort(self):
        """Test normalize extracts sort params."""
        query = {'portal_type': 'Document', 'sort_on': 'modified', 'sort_order': 'desc'}
        normalized, sort_by = self.assembler.normalize(query)
        self.assertNotIn('sort_on', normalized)
        self.assertIn('modified:desc', sort_by)
        self.assertIn('_text_match:desc', sort_by)

    def test_normalize_removes_pagination(self):
        """Test normalize removes pagination params."""
        query = {'portal_type': 'Document', 'b_size': 10, 'b_start': 20, 'sort_limit': 100}
        normalized, _ = self.assembler.normalize(query)
        self.assertNotIn('b_size', normalized)
        self.assertNotIn('b_start', normalized)
        self.assertNotIn('sort_limit', normalized)


if __name__ == '__main__':
    unittest.main()
