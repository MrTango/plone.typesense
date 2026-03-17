"""Real Typesense integration tests - NO mocks, uses real Typesense server.

These tests verify that plone.typesense works correctly with a real Typesense server.

IMPORTANT: These tests use the PLONE_TYPESENSE_REAL_FUNCTIONAL_TESTING layer which:
- Connects to real Typesense at localhost:8108 (configurable via env vars)
- Configures ts_only_indexes = ["Title", "Description", "SearchableText"]
- This means these 3 indexes are ONLY queried via Typesense, not portal_catalog

To run these tests:
1. Start Typesense:
   docker run -p 8108:8108 -v/tmp/typesense-data:/data typesense/typesense:latest --data-dir /data --api-key=xyz

2. Run tests:
   uv run pytest src/plone/typesense/tests/test_real_typesense_search.py -v
"""
import unittest
import transaction
import time

from plone import api
from plone.app.testing import setRoles, TEST_USER_ID
from plone.typesense.testing import PLONE_TYPESENSE_REAL_FUNCTIONAL_TESTING
from zope.component import getUtility
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from plone.typesense.queueprocessor import IndexProcessor


class TestRealTypesenseSearch(unittest.TestCase):
    """Test search functionality with real Typesense server.

    This test class verifies that:
    1. Documents can be created and indexed in Typesense
    2. Title search works correctly (searches middle of title)
    3. Description search works correctly
    4. SearchableText (fulltext) search works correctly (searches body text)
    5. Results are accurate with exact counts
    """

    layer = PLONE_TYPESENSE_REAL_FUNCTIONAL_TESTING

    def setUp(self):
        """Set up test fixture.

        Creates 3 documents with diverse content for testing different search scenarios.
        Each document has unique content in Title, Description, and Body to test
        that searches are correctly targeting specific fields.
        """
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

        # Get catalog for searching
        self.catalog = api.portal.get_tool("portal_catalog")

        # Get Typesense connector for rebuilding collection
        self.ts_connector = getUtility(ITypesenseConnector)

        # Create Document 1: About blockchain technology
        self.doc1 = api.content.create(
            container=self.portal,
            type="Document",
            id="doc1-blockchain",
            title="Blockchain Technology Overview and Applications",
            description="An introduction to distributed ledger systems and consensus",
            text="<p>This is a comprehensive guide to blockchain and cryptocurrency. "
                 "Understanding the fundamentals of decentralized networks.</p>"
        )

        # Create Document 2: About artificial intelligence
        self.doc2 = api.content.create(
            container=self.portal,
            type="Document",
            id="doc2-ai",
            title="Artificial Intelligence Basics and Future",
            description="Machine learning fundamentals and neural networks",
            text="<p>Deep neural networks are revolutionizing AI research. "
                 "Understanding convolutional and recurrent architectures.</p>"
        )

        # Create Document 3: About quantum computing
        self.doc3 = api.content.create(
            container=self.portal,
            type="Document",
            id="doc3-quantum",
            title="Quantum Computing Explained Simply",
            description="Quantum mechanics principles applied to computation",
            text="<p>Superposition and entanglement are key quantum phenomena. "
                 "Quantum gates enable complex calculations impossible for classical computers.</p>"
        )

        # Commit transaction to trigger indexing
        transaction.commit()

        # Rebuild Typesense collection to ensure clean state
        self.ts_connector.clear()

        # Explicitly index documents to Typesense using IndexProcessor
        processor = IndexProcessor()
        processor.index(self.doc1, attributes=None)
        processor.index(self.doc2, attributes=None)
        processor.index(self.doc3, attributes=None)
        processor.commit()

        # Give Typesense a moment to index
        time.sleep(0.5)

    def test_title_search_finds_document_by_middle_of_title(self):
        """Test that searching for a word in the middle of a title finds the correct document.

        Search for "intelligence" which appears in the middle of Document 2's title:
        "Artificial Intelligence Basics and Future"

        Should find ONLY Document 2.
        """
        results = self.catalog.searchResults(Title="intelligence")

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Title search should find only Document 2 which contains 'intelligence'."
        )
        self.assertEqual(results[0].getId, "doc2-ai")

    def test_description_search_finds_document_by_description_content(self):
        """Test that searching for a word in description finds the correct document.

        Search for "distributed" which appears only in Document 1's description.
        Should find ONLY Document 1.
        """
        results = self.catalog.searchResults(Description="distributed")

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Description search should find only Document 1 which contains 'distributed'."
        )
        self.assertEqual(results[0].getId, "doc1-blockchain")

    def test_searchabletext_search_finds_document_by_body_text(self):
        """Test that SearchableText search finds document by body text content.

        Search for "superposition" which appears only in Document 3's body text.
        Should find ONLY Document 3.
        """
        results = self.catalog.searchResults(SearchableText="superposition")

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"SearchableText search should find only Document 3 which contains 'superposition' in body."
        )
        self.assertEqual(results[0].getId, "doc3-quantum")

    def test_searchabletext_search_with_word_from_body(self):
        """Test that SearchableText finds document by word in body text.

        Search for "guide" which appears only in Document 1's body text.
        Should find ONLY Document 1.
        """
        results = self.catalog.searchResults(SearchableText="guide")

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"SearchableText search should find only Document 1 which contains 'guide' in body."
        )
        self.assertEqual(results[0].getId, "doc1-blockchain")

    def test_searchabletext_with_common_word_finds_multiple_documents(self):
        """Test that SearchableText finds multiple documents with common word.

        Search for "understanding" which appears in both Document 1 and Document 2.
        Should find both.
        """
        results = self.catalog.searchResults(SearchableText="understanding")

        result_ids = set()
        for brain in results:
            result_ids.add(brain.getId)

        self.assertEqual(
            len(results), 2,
            f"Expected exactly 2 results, got {len(results)}. "
            f"SearchableText search should find Documents 1 and 2 which contain 'understanding'."
        )

        expected_ids = {"doc1-blockchain", "doc2-ai"}
        self.assertEqual(result_ids, expected_ids)

    def test_title_search_case_insensitive(self):
        """Test that title search is case-insensitive.

        Search for "QUANTUM" (uppercase) should find Document 3 with title:
        "Quantum Computing Explained Simply"
        """
        results = self.catalog.searchResults(Title="QUANTUM")

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Case-insensitive title search should find Document 3."
        )
        self.assertEqual(results[0].getId, "doc3-quantum")

    def test_no_results_for_nonexistent_term(self):
        """Test that searching for a non-existent term returns no results."""
        results = self.catalog.searchResults(SearchableText="zzznonexistent")

        self.assertEqual(
            len(results), 0,
            f"Expected 0 results for non-existent term, got {len(results)}."
        )

    def test_combined_filter_and_text_search(self):
        """Test combining filter (portal_type) with text search.

        Search for portal_type=Document AND SearchableText="quantum".
        Should find only Document 3.
        """
        results = self.catalog.searchResults(
            portal_type="Document",
            SearchableText="quantum"
        )

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Combined search should find only Document 3."
        )
        self.assertEqual(results[0].getId, "doc3-quantum")

    def test_api_create_and_find_document(self):
        """Test that api.content.create + transaction.commit + api.content.find works.

        This test verifies the complete real-world workflow:
        1. Create document with plone.api.content.create()
        2. Commit transaction
        3. Document is automatically indexed to Typesense (via event subscriber)
        4. Search with plone.api.content.find() (internally uses catalog.searchResults())
        5. Monkey patch routes query to Typesense
        6. Document is found
        """
        from plone.app.textfield import RichTextValue

        new_doc = api.content.create(
            container=self.portal,
            type='Document',
            id='api-test-doc',
            title='Machine Learning Applications in Healthcare',
            description='Exploring AI in medical diagnostics',
            text=RichTextValue(
                raw='<p>Neural networks are transforming medical imaging and diagnosis.</p>',
                mimeType='text/html',
                outputMimeType='text/html',
            ),
        )

        transaction.commit()

        # Give Typesense a moment to index
        time.sleep(0.5)

        # Search by title keyword
        results = api.content.find(SearchableText='Healthcare')

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result for 'Healthcare' search, got {len(results)}"
        )
        self.assertEqual(results[0].getId, 'api-test-doc')
        self.assertIn('Machine Learning', results[0].Title)

        # Search by body text keyword
        results = api.content.find(SearchableText='diagnosis')

        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result for 'diagnosis' search, got {len(results)}"
        )
        self.assertEqual(results[0].getId, 'api-test-doc')


if __name__ == "__main__":
    unittest.main()
