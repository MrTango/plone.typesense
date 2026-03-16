"""Tests for Typesense-native query methods on index classes."""

import unittest
from unittest.mock import MagicMock

from plone.typesense.indexes import (
    BaseIndex,
    TBooleanIndex,
    TDateIndex,
    TFieldIndex,
    TKeywordIndex,
    TZCTextIndex,
)


class MockIndex:
    """Minimal mock for a Plone catalog index."""

    def __init__(self, name="test_field"):
        self.id = name

    def getIndexSourceNames(self):
        return [self.id]


class TestBaseIndexNegation(unittest.TestCase):
    """Test _detect_negation and _normalize_query on BaseIndex."""

    def setUp(self):
        self.idx = BaseIndex(None, MockIndex())

    def test_normalize_dict_with_query_key(self):
        result = self.idx._normalize_query({"query": "hello"})
        self.assertEqual(result, "hello")

    def test_normalize_plain_string(self):
        result = self.idx._normalize_query("hello")
        self.assertEqual(result, "hello")

    def test_detect_negation_not_key(self):
        negated, value = self.idx._detect_negation({"not": "Folder"})
        self.assertTrue(negated)
        self.assertEqual(value, "Folder")

    def test_detect_negation_operator_not(self):
        negated, value = self.idx._detect_negation(
            {"operator": "not", "query": "Folder"}
        )
        self.assertTrue(negated)
        self.assertEqual(value, "Folder")

    def test_detect_negation_no_negation(self):
        negated, value = self.idx._detect_negation({"query": "hello"})
        self.assertFalse(negated)

    def test_detect_negation_plain_string(self):
        negated, value = self.idx._detect_negation("hello")
        self.assertFalse(negated)
        self.assertEqual(value, "hello")


class TestBaseIndexTsFilter(unittest.TestCase):
    """Test get_ts_filter on BaseIndex."""

    def setUp(self):
        self.idx = BaseIndex(None, MockIndex("portal_type"))

    def test_simple_equals(self):
        result = self.idx.get_ts_filter("portal_type", "Document")
        self.assertEqual(result, "portal_type:=`Document`")

    def test_list_equals(self):
        result = self.idx.get_ts_filter("portal_type", ["Document", "File"])
        self.assertEqual(result, "portal_type:[`Document`, `File`]")

    def test_negation(self):
        result = self.idx.get_ts_filter("portal_type", {"not": "Folder"})
        self.assertEqual(result, "portal_type:!=`Folder`")

    def test_negation_list(self):
        result = self.idx.get_ts_filter(
            "portal_type", {"not": ["Folder", "Collection"]}
        )
        self.assertEqual(result, "portal_type:!=[`Folder`, `Collection`]")

    def test_operator_not(self):
        result = self.idx.get_ts_filter(
            "portal_type", {"operator": "not", "query": "Folder"}
        )
        self.assertEqual(result, "portal_type:!=`Folder`")


class TestBaseIndexTsQuery(unittest.TestCase):
    """Test get_ts_query on BaseIndex (filter-based indexes)."""

    def setUp(self):
        self.idx = BaseIndex(None, MockIndex("review_state"))

    def test_returns_filter_by(self):
        result = self.idx.get_ts_query("review_state", "published")
        self.assertIn("filter_by", result)
        self.assertEqual(result["filter_by"], "review_state:=`published`")


class TestTKeywordIndexTsFilter(unittest.TestCase):
    """Test TKeywordIndex.get_ts_filter."""

    def setUp(self):
        self.idx = TKeywordIndex(None, MockIndex("Subject"))

    def test_single_keyword(self):
        result = self.idx.get_ts_filter("Subject", "python")
        self.assertEqual(result, "Subject:=`python`")

    def test_multiple_keywords(self):
        result = self.idx.get_ts_filter("Subject", ["python", "plone"])
        self.assertEqual(result, "Subject:[`python`, `plone`]")

    def test_negated_keyword(self):
        result = self.idx.get_ts_filter("Subject", {"not": "internal"})
        self.assertEqual(result, "Subject:!=`internal`")

    def test_negated_keywords_list(self):
        result = self.idx.get_ts_filter(
            "Subject", {"not": ["internal", "draft"]}
        )
        self.assertEqual(result, "Subject:!=[`internal`, `draft`]")


class TestTBooleanIndexTsFilter(unittest.TestCase):
    """Test TBooleanIndex.get_ts_filter."""

    def setUp(self):
        self.idx = TBooleanIndex(None, MockIndex("is_folderish"))

    def test_true(self):
        result = self.idx.get_ts_filter("is_folderish", True)
        self.assertEqual(result, "is_folderish:=true")

    def test_false(self):
        result = self.idx.get_ts_filter("is_folderish", False)
        self.assertEqual(result, "is_folderish:=false")

    def test_negated(self):
        result = self.idx.get_ts_filter("is_folderish", {"not": True})
        self.assertEqual(result, "is_folderish:!=true")


class TestTZCTextIndexTsQuery(unittest.TestCase):
    """Test TZCTextIndex.get_ts_query — phrase matching, boost, negation."""

    def setUp(self):
        self.idx = TZCTextIndex(None, MockIndex("SearchableText"))

    def test_simple_text_query(self):
        result = self.idx.get_ts_query("SearchableText", "plone cms")
        self.assertIn("q", result)
        self.assertEqual(result["q"], "plone cms")
        # SearchableText should also search Title with boost
        self.assertIn("query_by", result)
        self.assertIn("Title", result["query_by"])
        self.assertIn("SearchableText", result["query_by"])

    def test_title_query_boost(self):
        idx = TZCTextIndex(None, MockIndex("Title"))
        result = idx.get_ts_query("Title", "my document")
        self.assertEqual(result["q"], "my document")
        self.assertEqual(result["query_by"], "Title")
        self.assertEqual(result["query_by_weights"], "2")

    def test_strip_wildcards(self):
        result = self.idx.get_ts_query("SearchableText", "*plone*")
        self.assertEqual(result["q"], "plone")

    def test_phrase_matching(self):
        result = self.idx.get_ts_query("SearchableText", '"exact phrase"')
        self.assertEqual(result["q"], '"exact phrase"')

    def test_negation_produces_filter(self):
        result = self.idx.get_ts_query(
            "SearchableText", {"not": "unwanted"}
        )
        self.assertIn("filter_by", result)
        self.assertIn("!=", result["filter_by"])
        self.assertNotIn("q", result)

    def test_empty_query_returns_none(self):
        result = self.idx.get_ts_query("SearchableText", "***")
        self.assertIsNone(result)

    def test_dict_with_query_key(self):
        result = self.idx.get_ts_query(
            "SearchableText", {"query": "plone cms"}
        )
        self.assertEqual(result["q"], "plone cms")

    def test_other_field_no_title_boost(self):
        idx = TZCTextIndex(None, MockIndex("Description"))
        result = idx.get_ts_query("Description", "some text")
        self.assertEqual(result["query_by"], "Description")
        self.assertNotIn("Title", result.get("query_by", ""))

    def test_short_query_enables_infix(self):
        result = self.idx.get_ts_query("SearchableText", "ab")
        self.assertEqual(result.get("infix"), "always")


class TestTDateIndexTsFilter(unittest.TestCase):
    """Test TDateIndex.get_ts_filter."""

    def setUp(self):
        self.idx = TDateIndex(None, MockIndex("modified"))

    def test_range_min(self):
        from DateTime import DateTime as DT

        result = self.idx.get_ts_filter(
            "modified", {"query": DT("2024/01/01"), "range": "min"}
        )
        self.assertIn("modified:>=", result)

    def test_range_max(self):
        from DateTime import DateTime as DT

        result = self.idx.get_ts_filter(
            "modified", {"query": DT("2024/12/31"), "range": "max"}
        )
        self.assertIn("modified:<=", result)

    def test_range_minmax(self):
        from DateTime import DateTime as DT

        result = self.idx.get_ts_filter(
            "modified",
            {
                "query": [DT("2024/01/01"), DT("2024/12/31")],
                "range": "min:max",
            },
        )
        self.assertIn("modified:[", result)
        self.assertIn("..", result)

    def test_no_query_returns_none(self):
        result = self.idx.get_ts_filter("modified", {"range": "min"})
        self.assertIsNone(result)


class TestFieldIndexTsFilter(unittest.TestCase):
    """Test TFieldIndex inherits BaseIndex.get_ts_filter."""

    def setUp(self):
        self.idx = TFieldIndex(None, MockIndex("review_state"))

    def test_simple(self):
        result = self.idx.get_ts_filter("review_state", "published")
        self.assertEqual(result, "review_state:=`published`")

    def test_negation(self):
        result = self.idx.get_ts_filter(
            "review_state", {"not": "private"}
        )
        self.assertEqual(result, "review_state:!=`private`")


if __name__ == "__main__":
    unittest.main()
