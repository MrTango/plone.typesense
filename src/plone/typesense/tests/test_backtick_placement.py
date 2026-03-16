"""Test backtick placement in Typesense filter syntax."""
import unittest
from plone.typesense.indexes import TKeywordIndex


class TestBacktickPlacement(unittest.TestCase):
    """Test that backticks are placed correctly in list filters."""

    def setUp(self):
        """Set up a mock catalog and index for testing."""
        # Create a minimal mock catalog
        class MockCatalog:
            pass

        # Create a minimal mock index
        class MockIndex:
            def __init__(self):
                self.id = 'portal_type'

            def getIndexSourceNames(self):
                return ['portal_type']

        self.catalog = MockCatalog()
        self.mock_index = MockIndex()
        self.index = TKeywordIndex(self.catalog, self.mock_index)

    def test_single_value_no_spaces(self):
        """Test single value without spaces - ALL values get backticks."""
        result = self.index.get_ts_filter('portal_type', 'Document')
        self.assertEqual(result, 'portal_type:=`Document`')
        print(f"\nTest 1 - Single value no spaces: {result}")

    def test_single_value_with_spaces(self):
        """Test single value with spaces - ALL values get backticks."""
        result = self.index.get_ts_filter('portal_type', 'News Item')
        self.assertEqual(result, 'portal_type:=`News Item`')
        print(f"\nTest 2 - Single value with spaces: {result}")

    def test_list_no_spaces(self):
        """Test list of values without spaces - ALL values get backticks."""
        result = self.index.get_ts_filter('portal_type', ['Document', 'Folder', 'Link'])
        self.assertEqual(result, 'portal_type:[`Document`, `Folder`, `Link`]')
        print(f"\nTest 3 - List no spaces: {result}")

    def test_list_with_spaces(self):
        """Test list of values with some having spaces - ALL values get backticks."""
        result = self.index.get_ts_filter('portal_type', ['Document', 'News Item', 'Collection'])
        # According to Typesense filter syntax, ALL string values need backticks
        self.assertEqual(result, 'portal_type:[`Document`, `News Item`, `Collection`]')
        print(f"\nTest 4 - List with spaces: {result}")

    def test_list_all_with_spaces(self):
        """Test list of values all having spaces - ALL values get backticks."""
        result = self.index.get_ts_filter('portal_type', ['News Item', 'Event Item'])
        self.assertEqual(result, 'portal_type:[`News Item`, `Event Item`]')
        print(f"\nTest 5 - List all with spaces: {result}")

    def test_dict_query_single_value(self):
        """Test dict query with single value - ALL values get backticks."""
        result = self.index.get_ts_filter('portal_type', {'query': 'Document', 'operator': 'or'})
        self.assertEqual(result, 'portal_type:=`Document`')
        print(f"\nTest 6 - Dict query single value: {result}")

    def test_dict_query_list(self):
        """Test dict query with list of values - ALL values get backticks."""
        result = self.index.get_ts_filter(
            'portal_type',
            {'query': ['Document', 'News Item', 'Folder'], 'operator': 'or'}
        )
        self.assertEqual(result, 'portal_type:[`Document`, `News Item`, `Folder`]')
        print(f"\nTest 7 - Dict query with list: {result}")

    def test_tuple_input(self):
        """Test tuple input (should work like list) - ALL values get backticks."""
        result = self.index.get_ts_filter('portal_type', ('Document', 'News Item'))
        self.assertEqual(result, 'portal_type:[`Document`, `News Item`]')
        print(f"\nTest 8 - Tuple input: {result}")

    def test_set_input(self):
        """Test set input (should work like list) - ALL values get backticks."""
        # Note: Sets are unordered, so we can't guarantee order
        result = self.index.get_ts_filter('portal_type', {'Document', 'Folder'})
        # Just check it's in the list format with backticks
        self.assertTrue(result.startswith('portal_type:['))
        self.assertTrue(result.endswith(']'))
        # Check that values are wrapped in backticks
        self.assertIn('`Document`', result)
        self.assertIn('`Folder`', result)
        print(f"\nTest 9 - Set input: {result}")

    def test_real_world_example(self):
        """Test the exact format from the indexing-strategies.md story file."""
        portal_types = ['File', 'Collection', 'Document', 'Folder', 'Image', 'Event', 'Link', 'News Item']
        result = self.index.get_ts_filter('portal_type', portal_types)
        expected = 'portal_type:[`File`, `Collection`, `Document`, `Folder`, `Image`, `Event`, `Link`, `News Item`]'
        self.assertEqual(result, expected)
        print(f"\nTest 10 - Real world example: {result}")


if __name__ == '__main__':
    unittest.main()
