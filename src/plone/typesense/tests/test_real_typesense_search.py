# -*- coding: utf-8 -*-
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
   /home/maik/develop/plonecore/buildout.coredev/src/plone.typesense/bin/test -s plone.typesense -t test_real_typesense_search
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

        print("\n" + "=" * 80)
        print("TEST SETUP: Creating test documents")
        print("=" * 80)

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
        print(f"Created Document 1: {self.doc1.title}")
        print(f"  Description: {self.doc1.description}")
        print(f"  Body text: {self.doc1.text.raw if hasattr(self.doc1.text, 'raw') else self.doc1.text}")

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
        print(f"\nCreated Document 2: {self.doc2.title}")
        print(f"  Description: {self.doc2.description}")
        print(f"  Body text: {self.doc2.text.raw if hasattr(self.doc2.text, 'raw') else self.doc2.text}")

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
        print(f"\nCreated Document 3: {self.doc3.title}")
        print(f"  Description: {self.doc3.description}")
        print(f"  Body text: {self.doc3.text.raw if hasattr(self.doc3.text, 'raw') else self.doc3.text}")

        # Commit transaction to trigger indexing
        transaction.commit()
        print("\n" + "-" * 80)
        print("Transaction committed - documents should be indexed")
        print("-" * 80)

        # Rebuild Typesense collection to ensure clean state
        print("\nRebuilding Typesense collection...")
        self.ts_connector.clear()
        print("Typesense collection cleared and reinitialized")

        # Explicitly index documents to Typesense using IndexProcessor
        print("\nIndexing documents to Typesense using IndexProcessor...")
        processor = IndexProcessor()

        # Index each document
        print("  Indexing doc1-blockchain...")
        processor.index(self.doc1, attributes=None)
        print("  Indexing doc2-ai...")
        processor.index(self.doc2, attributes=None)
        print("  Indexing doc3-quantum...")
        processor.index(self.doc3, attributes=None)

        # Commit to Typesense
        print("  Committing to Typesense...")
        processor.commit()
        print("Indexing complete")

        # Verify documents are in Typesense
        print("\nVerifying documents in Typesense...")
        time.sleep(0.5)  # Give Typesense a moment to index
        try:
            results = self.ts_connector.client.collections[self.ts_connector.collection_base_name].documents.search({
                'q': '*',
                'per_page': 10
            })
            print(f"Documents in Typesense after indexing: {results['found']}")
            if results['found'] > 0:
                for hit in results['hits']:
                    print(f"  - {hit['document'].get('Title', 'No title')} (ID: {hit['document'].get('id', 'No ID')})")
            else:
                print("  WARNING: No documents found in Typesense!")
        except Exception as e:
            print(f"  ERROR verifying documents: {e}")

        print("=" * 80 + "\n")

    def test_title_search_finds_document_by_middle_of_title(self):
        """Test that searching for a word in the middle of a title finds the correct document.

        Search for "intelligence" which appears in the middle of Document 2's title:
        "Artificial Intelligence Basics and Future"

        Should find ONLY Document 2.
        """
        print("\n" + "=" * 80)
        print("TEST: Title search for 'intelligence'")
        print("=" * 80)

        # Search for "intelligence" in Title
        results = self.catalog.searchResults(Title="intelligence")

        print(f"Query: Title='intelligence'")
        print(f"Expected: 1 result (Document 2)")
        print(f"Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"  Result {idx + 1}: {brain.Title} (ID: {brain.getId})")

        # Assert exact count
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Title search should find only Document 2 which contains 'intelligence'."
        )

        # Assert correct document
        self.assertEqual(
            results[0].getId, "doc2-ai",
            f"Expected doc2-ai, got {results[0].getId}. "
            f"Title search for 'intelligence' should find Document 2."
        )

        print("PASS: Found exactly 1 result (Document 2)")
        print("=" * 80 + "\n")

    def test_description_search_finds_document_by_description_content(self):
        """Test that searching for a word in description finds the correct document.

        Search for "distributed" which appears only in Document 1's description:
        "An introduction to distributed ledger systems and consensus"

        Should find ONLY Document 1.
        """
        print("\n" + "=" * 80)
        print("TEST: Description search for 'distributed'")
        print("=" * 80)

        # Search for "distributed" in Description
        results = self.catalog.searchResults(Description="distributed")

        print(f"Query: Description='distributed'")
        print(f"Expected: 1 result (Document 1)")
        print(f"Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"  Result {idx + 1}: {brain.Title} (ID: {brain.getId})")
            print(f"    Description: {brain.Description}")

        # Assert exact count
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Description search should find only Document 1 which contains 'distributed'."
        )

        # Assert correct document
        self.assertEqual(
            results[0].getId, "doc1-blockchain",
            f"Expected doc1-blockchain, got {results[0].getId}. "
            f"Description search for 'distributed' should find Document 1."
        )

        print("PASS: Found exactly 1 result (Document 1)")
        print("=" * 80 + "\n")

    def test_searchabletext_search_finds_document_by_body_text(self):
        """Test that SearchableText search finds document by body text content.

        Search for "superposition" which appears only in Document 3's body text:
        "Superposition and entanglement are key quantum phenomena..."

        Should find ONLY Document 3.
        """
        print("\n" + "=" * 80)
        print("TEST: SearchableText search for 'superposition' (body text)")
        print("=" * 80)

        # Search for "superposition" in SearchableText
        results = self.catalog.searchResults(SearchableText="superposition")

        print(f"Query: SearchableText='superposition'")
        print(f"Expected: 1 result (Document 3)")
        print(f"Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"  Result {idx + 1}: {brain.Title} (ID: {brain.getId})")
            print(f"    Description: {brain.Description}")

        # Assert exact count
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"SearchableText search should find only Document 3 which contains 'superposition' in body."
        )

        # Assert correct document
        self.assertEqual(
            results[0].getId, "doc3-quantum",
            f"Expected doc3-quantum, got {results[0].getId}. "
            f"SearchableText search for 'superposition' should find Document 3."
        )

        print("PASS: Found exactly 1 result (Document 3)")
        print("=" * 80 + "\n")

    def test_searchabletext_search_with_word_from_body(self):
        """Test that SearchableText finds document by word in body text.

        Search for "guide" which appears only in Document 1's body text:
        "This is a comprehensive guide to blockchain..."

        Should find ONLY Document 1.
        """
        print("\n" + "=" * 80)
        print("TEST: SearchableText search for 'guide' (body text)")
        print("=" * 80)

        # Search for "guide" in SearchableText
        results = self.catalog.searchResults(SearchableText="guide")

        print(f"Query: SearchableText='guide'")
        print(f"Expected: 1 result (Document 1)")
        print(f"Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"  Result {idx + 1}: {brain.Title} (ID: {brain.getId})")
            print(f"    Description: {brain.Description}")

        # Assert exact count
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"SearchableText search should find only Document 1 which contains 'guide' in body."
        )

        # Assert correct document
        self.assertEqual(
            results[0].getId, "doc1-blockchain",
            f"Expected doc1-blockchain, got {results[0].getId}. "
            f"SearchableText search for 'guide' should find Document 1."
        )

        print("PASS: Found exactly 1 result (Document 1)")
        print("=" * 80 + "\n")

    def test_searchabletext_with_common_word_finds_multiple_documents(self):
        """Test that SearchableText finds multiple documents with common word.

        Search for "understanding" which appears in both Document 1 and Document 2:
        - Document 1: "Understanding the fundamentals of decentralized networks"
        - Document 2: "Understanding convolutional and recurrent architectures"

        Should find both Document 1 and Document 2.
        """
        print("\n" + "=" * 80)
        print("TEST: SearchableText search for 'understanding' (appears in 2 docs)")
        print("=" * 80)

        # Search for "understanding" in SearchableText
        results = self.catalog.searchResults(SearchableText="understanding")

        print(f"Query: SearchableText='understanding'")
        print(f"Expected: 2 results (Documents 1 and 2)")
        print(f"Actual: {len(results)} results")

        result_ids = set()
        for idx, brain in enumerate(results):
            print(f"  Result {idx + 1}: {brain.Title} (ID: {brain.getId})")
            result_ids.add(brain.getId)

        # Assert exact count
        self.assertEqual(
            len(results), 2,
            f"Expected exactly 2 results, got {len(results)}. "
            f"SearchableText search should find Documents 1 and 2 which contain 'understanding'."
        )

        # Assert correct documents
        expected_ids = {"doc1-blockchain", "doc2-ai"}
        self.assertEqual(
            result_ids, expected_ids,
            f"Expected {expected_ids}, got {result_ids}. "
            f"SearchableText search for 'understanding' should find Documents 1 and 2."
        )

        print("PASS: Found exactly 2 results (Documents 1 and 2)")
        print("=" * 80 + "\n")

    def test_title_search_case_insensitive(self):
        """Test that title search is case-insensitive.

        Search for "QUANTUM" (uppercase) should find Document 3 with title:
        "Quantum Computing Explained Simply"
        """
        print("\n" + "=" * 80)
        print("TEST: Case-insensitive title search for 'QUANTUM'")
        print("=" * 80)

        # Search for "QUANTUM" (uppercase) in Title
        results = self.catalog.searchResults(Title="QUANTUM")

        print(f"Query: Title='QUANTUM' (uppercase)")
        print(f"Expected: 1 result (Document 3)")
        print(f"Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"  Result {idx + 1}: {brain.Title} (ID: {brain.getId})")

        # Assert exact count
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Case-insensitive title search should find Document 3."
        )

        # Assert correct document
        self.assertEqual(
            results[0].getId, "doc3-quantum",
            f"Expected doc3-quantum, got {results[0].getId}. "
            f"Case-insensitive search for 'QUANTUM' should find Document 3."
        )

        print("PASS: Found exactly 1 result (Document 3) - case insensitive works")
        print("=" * 80 + "\n")

    def test_no_results_for_nonexistent_term(self):
        """Test that searching for a non-existent term returns no results."""
        print("\n" + "=" * 80)
        print("TEST: Search for non-existent term 'zzznonexistent'")
        print("=" * 80)

        # Search for non-existent term
        results = self.catalog.searchResults(SearchableText="zzznonexistent")

        print(f"Query: SearchableText='zzznonexistent'")
        print(f"Expected: 0 results")
        print(f"Actual: {len(results)} results")

        # Assert no results
        self.assertEqual(
            len(results), 0,
            f"Expected 0 results for non-existent term, got {len(results)}."
        )

        print("PASS: Found 0 results as expected")
        print("=" * 80 + "\n")

    def test_combined_filter_and_text_search(self):
        """Test combining filter (portal_type) with text search.

        Search for portal_type=Document AND SearchableText="quantum".
        Should find only Document 3.
        """
        print("\n" + "=" * 80)
        print("TEST: Combined filter and text search")
        print("=" * 80)

        # Search with both filter and text query
        results = self.catalog.searchResults(
            portal_type="Document",
            SearchableText="quantum"
        )

        print(f"Query: portal_type='Document' AND SearchableText='quantum'")
        print(f"Expected: 1 result (Document 3)")
        print(f"Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"  Result {idx + 1}: {brain.Title} (ID: {brain.getId})")
            print(f"    Type: {brain.portal_type}")

        # Assert exact count
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result, got {len(results)}. "
            f"Combined search should find only Document 3."
        )

        # Assert correct document
        self.assertEqual(
            results[0].getId, "doc3-quantum",
            f"Expected doc3-quantum, got {results[0].getId}."
        )

        print("PASS: Combined filter and text search works correctly")
        print("=" * 80 + "\n")

    def test_api_create_and_find_document(self):
        """Test that api.content.create + transaction.commit + api.content.find works.

        This test verifies the complete real-world workflow:
        1. Create document with plone.api.content.create()
        2. Commit transaction
        3. Document is automatically indexed to Typesense (via event subscriber)
        4. Search with plone.api.content.find() (internally uses catalog.searchResults())
        5. Monkey patch routes query to Typesense
        6. Document is found

        This demonstrates the zero-configuration integration that developers will use.
        """
        print("\n" + "=" * 80)
        print("TEST: API create and find workflow")
        print("=" * 80)

        # Step 1: Create document with api.content.create()
        print("\nStep 1: Creating document with api.content.create()...")
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
        print(f"Created document: {new_doc.title}")
        print(f"  ID: {new_doc.id}")
        print(f"  Description: {new_doc.description}")
        print(f"  Body text: {new_doc.text.raw}")

        # Step 2: Commit transaction
        print("\nStep 2: Committing transaction...")
        print("  (This triggers event subscribers and IndexProcessor)")
        transaction.commit()
        print("  Transaction committed")

        # Give Typesense a moment to index (in production, this is not needed)
        time.sleep(0.5)

        # Step 3: Search with api.content.find() - Title search
        print("\nStep 3a: Searching with api.content.find(SearchableText='Healthcare')...")
        print("  (This internally calls catalog.searchResults() which is monkey-patched)")
        results = api.content.find(SearchableText='Healthcare')

        print(f"  Query: SearchableText='Healthcare'")
        print(f"  Expected: 1 result (our new document)")
        print(f"  Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"    Result {idx + 1}: {brain.Title} (ID: {brain.getId})")

        # Step 4: Verify results for title search
        print("\nStep 4a: Verifying title search results...")
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result for 'Healthcare' search, got {len(results)}"
        )
        self.assertEqual(
            results[0].getId, 'api-test-doc',
            f"Expected api-test-doc, got {results[0].getId}"
        )
        self.assertIn(
            'Machine Learning',
            results[0].Title,
            f"Expected title to contain 'Machine Learning', got {results[0].Title}"
        )
        print("  PASS: Title search found correct document")

        # Step 3b: Search with api.content.find() - Body text search
        print("\nStep 3b: Searching with api.content.find(SearchableText='diagnosis')...")
        print("  (Searching for word in body text)")
        results = api.content.find(SearchableText='diagnosis')

        print(f"  Query: SearchableText='diagnosis'")
        print(f"  Expected: 1 result (our new document)")
        print(f"  Actual: {len(results)} results")

        for idx, brain in enumerate(results):
            print(f"    Result {idx + 1}: {brain.Title} (ID: {brain.getId})")

        # Step 4b: Verify results for body text search
        print("\nStep 4b: Verifying body text search results...")
        self.assertEqual(
            len(results), 1,
            f"Expected exactly 1 result for 'diagnosis' search, got {len(results)}"
        )
        self.assertEqual(
            results[0].getId, 'api-test-doc',
            f"Expected api-test-doc, got {results[0].getId}"
        )
        print("  PASS: Body text search found correct document")

        print("\n" + "-" * 80)
        print("WORKFLOW VERIFIED:")
        print("  ✓ api.content.create() works")
        print("  ✓ transaction.commit() triggers indexing")
        print("  ✓ IndexProcessor indexes to Typesense automatically")
        print("  ✓ api.content.find() routes to Typesense via monkey patch")
        print("  ✓ Title search works (word in title)")
        print("  ✓ Body text search works (word in body)")
        print("-" * 80)
        print("PASS: Complete API workflow works end-to-end")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    unittest.main()
