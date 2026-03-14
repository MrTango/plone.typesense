"""Tests for synonym parsing and syncing."""

import unittest
from unittest.mock import MagicMock, patch

from plone.typesense.synonyms import parse_synonyms, sync_synonyms


class TestParseSynonyms(unittest.TestCase):
    """Test synonym text parsing."""

    def test_empty_input(self):
        self.assertEqual(parse_synonyms(""), [])
        self.assertEqual(parse_synonyms(None), [])

    def test_multi_way_synonym(self):
        result = parse_synonyms("blazer, jacket, coat")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["synonyms"], ["blazer", "jacket", "coat"])
        self.assertNotIn("root", result[0])

    def test_one_way_synonym(self):
        result = parse_synonyms("blazer => jacket, coat")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["root"], "blazer")
        self.assertEqual(result[0]["synonyms"], ["jacket", "coat"])

    def test_multiple_rules(self):
        text = """blazer, jacket, coat
pants => trousers, slacks
shoe, sneaker, boot"""
        result = parse_synonyms(text)
        self.assertEqual(len(result), 3)

        # First rule: multi-way
        self.assertEqual(result[0]["synonyms"], ["blazer", "jacket", "coat"])
        self.assertNotIn("root", result[0])

        # Second rule: one-way
        self.assertEqual(result[1]["root"], "pants")
        self.assertEqual(result[1]["synonyms"], ["trousers", "slacks"])

        # Third rule: multi-way
        self.assertEqual(result[2]["synonyms"], ["shoe", "sneaker", "boot"])

    def test_comments_ignored(self):
        text = """# This is a comment
blazer, jacket
# Another comment
shoe, sneaker"""
        result = parse_synonyms(text)
        self.assertEqual(len(result), 2)

    def test_empty_lines_ignored(self):
        text = """blazer, jacket

shoe, sneaker

"""
        result = parse_synonyms(text)
        self.assertEqual(len(result), 2)

    def test_whitespace_handling(self):
        result = parse_synonyms("  blazer ,  jacket ,  coat  ")
        self.assertEqual(result[0]["synonyms"], ["blazer", "jacket", "coat"])

    def test_single_word_ignored(self):
        result = parse_synonyms("onlyoneword")
        self.assertEqual(len(result), 0)

    def test_one_way_with_empty_root_ignored(self):
        result = parse_synonyms(" => jacket, coat")
        self.assertEqual(len(result), 0)

    def test_one_way_with_empty_synonyms_ignored(self):
        result = parse_synonyms("blazer =>  ")
        self.assertEqual(len(result), 0)

    def test_synonym_ids_are_unique(self):
        text = """blazer, jacket
shoe, sneaker
pants, trousers"""
        result = parse_synonyms(text)
        ids = [r["id"] for r in result]
        self.assertEqual(len(ids), len(set(ids)))


class TestSyncSynonyms(unittest.TestCase):
    """Test synonym syncing to Typesense."""

    def _make_client(self, existing_synonyms=None):
        """Create a mock Typesense client."""
        client = MagicMock()
        collection = MagicMock()
        client.collections.__getitem__ = MagicMock(return_value=collection)

        synonyms_resource = MagicMock()
        collection.synonyms = synonyms_resource
        synonyms_resource.retrieve.return_value = {
            "synonyms": existing_synonyms or []
        }

        return client, collection, synonyms_resource

    def test_sync_new_synonyms(self):
        client, collection, synonyms_resource = self._make_client()
        rules = parse_synonyms("blazer, jacket, coat")
        upserted, errors = sync_synonyms(client, "test_collection", rules)
        self.assertEqual(upserted, 1)
        self.assertEqual(errors, [])
        synonyms_resource.upsert.assert_called_once()

    def test_sync_removes_existing_before_adding(self):
        existing = [{"id": "old-synonym-1"}, {"id": "old-synonym-2"}]
        client, collection, synonyms_resource = self._make_client(existing)

        rules = parse_synonyms("blazer, jacket")
        upserted, errors = sync_synonyms(client, "test_collection", rules)

        # Verify old synonyms were deleted
        self.assertEqual(
            synonyms_resource.__getitem__.call_count, 2
        )

    def test_sync_empty_rules_clears_synonyms(self):
        existing = [{"id": "old-synonym-1"}]
        client, collection, synonyms_resource = self._make_client(existing)

        upserted, errors = sync_synonyms(client, "test_collection", [])
        self.assertEqual(upserted, 0)
        self.assertEqual(errors, [])

    def test_sync_handles_upsert_error(self):
        client, collection, synonyms_resource = self._make_client()
        synonyms_resource.upsert.side_effect = Exception("API error")

        rules = parse_synonyms("blazer, jacket, coat")
        upserted, errors = sync_synonyms(client, "test_collection", rules)
        self.assertEqual(upserted, 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("API error", errors[0])

    def test_sync_multi_way_synonym_data(self):
        client, collection, synonyms_resource = self._make_client()
        rules = parse_synonyms("blazer, jacket, coat")
        sync_synonyms(client, "test_collection", rules)

        call_args = synonyms_resource.upsert.call_args
        synonym_id = call_args[0][0]
        synonym_data = call_args[0][1]
        self.assertIn("synonym-rule-", synonym_id)
        self.assertEqual(synonym_data["synonyms"], ["blazer", "jacket", "coat"])
        self.assertNotIn("root", synonym_data)

    def test_sync_one_way_synonym_data(self):
        client, collection, synonyms_resource = self._make_client()
        rules = parse_synonyms("blazer => jacket, coat")
        sync_synonyms(client, "test_collection", rules)

        call_args = synonyms_resource.upsert.call_args
        synonym_data = call_args[0][1]
        self.assertEqual(synonym_data["root"], "blazer")
        self.assertEqual(synonym_data["synonyms"], ["jacket", "coat"])


if __name__ == "__main__":
    unittest.main()
