"""Tests for TypesenseFilterBuilder."""

import unittest

from plone.typesense.filters import TypesenseFilterBuilder


class TestTypesenseFilterBuilder(unittest.TestCase):
    """Unit tests for the filter builder."""

    def setUp(self):
        self.fb = TypesenseFilterBuilder()

    # -- equals --------------------------------------------------------------

    def test_equals_string(self):
        result = self.fb.equals("portal_type", "Document").build()
        self.assertEqual(result, "portal_type:=`Document`")

    def test_equals_integer(self):
        result = self.fb.equals("age", 42).build()
        self.assertEqual(result, "age:=42")

    def test_equals_boolean(self):
        result = self.fb.equals("is_folderish", True).build()
        self.assertEqual(result, "is_folderish:=true")

    def test_equals_list(self):
        result = self.fb.equals("portal_type", ["Document", "News Item"]).build()
        self.assertEqual(result, "portal_type:[`Document`, `News Item`]")

    def test_equals_tuple(self):
        result = self.fb.equals("status", ("published", "private")).build()
        self.assertEqual(result, "status:[`published`, `private`]")

    # -- not_equals ----------------------------------------------------------

    def test_not_equals_string(self):
        result = self.fb.not_equals("portal_type", "Folder").build()
        self.assertEqual(result, "portal_type:!=`Folder`")

    def test_not_equals_list(self):
        result = self.fb.not_equals("status", ["draft", "private"]).build()
        self.assertEqual(result, "status:!=[`draft`, `private`]")

    # -- comparison operators ------------------------------------------------

    def test_greater_than(self):
        result = self.fb.greater_than("modified", 1700000000).build()
        self.assertEqual(result, "modified:>1700000000")

    def test_greater_equal(self):
        result = self.fb.greater_equal("rating", 3.5).build()
        self.assertEqual(result, "rating:>=3.5")

    def test_less_than(self):
        result = self.fb.less_than("price", 100).build()
        self.assertEqual(result, "price:<100")

    def test_less_equal(self):
        result = self.fb.less_equal("age", 65).build()
        self.assertEqual(result, "age:<=65")

    # -- range ---------------------------------------------------------------

    def test_range(self):
        result = self.fb.range("price", 10, 100).build()
        self.assertEqual(result, "price:[10..100]")

    # -- raw -----------------------------------------------------------------

    def test_raw(self):
        result = self.fb.raw("custom_field:=`special value`").build()
        self.assertEqual(result, "custom_field:=`special value`")

    def test_raw_empty_string_ignored(self):
        self.fb.raw("")
        self.assertEqual(len(self.fb), 0)

    # -- chaining and joining ------------------------------------------------

    def test_chaining_and(self):
        result = (
            self.fb
            .equals("portal_type", "Document")
            .equals("review_state", "published")
            .build()
        )
        self.assertEqual(
            result,
            "portal_type:=`Document` && review_state:=`published`",
        )

    def test_chaining_or(self):
        result = (
            self.fb
            .equals("portal_type", "Document")
            .equals("portal_type", "News Item")
            .build(join="||")
        )
        self.assertEqual(
            result,
            "portal_type:=`Document` || portal_type:=`News Item`",
        )

    def test_empty_build(self):
        self.assertEqual(self.fb.build(), "")

    # -- bool and len --------------------------------------------------------

    def test_bool_empty(self):
        self.assertFalse(self.fb)

    def test_bool_non_empty(self):
        self.fb.equals("x", 1)
        self.assertTrue(self.fb)

    def test_len(self):
        self.fb.equals("a", 1).equals("b", 2).not_equals("c", 3)
        self.assertEqual(len(self.fb), 3)

    # -- str and repr --------------------------------------------------------

    def test_str(self):
        self.fb.equals("x", 1)
        self.assertEqual(str(self.fb), "x:=1")

    def test_repr(self):
        self.fb.equals("x", 1)
        r = repr(self.fb)
        self.assertIn("TypesenseFilterBuilder", r)
        self.assertIn("x:=1", r)

    # -- validation ----------------------------------------------------------

    def test_invalid_field_name_empty(self):
        with self.assertRaises(ValueError):
            self.fb.equals("", "value")

    def test_invalid_field_name_special_chars(self):
        with self.assertRaises(ValueError):
            self.fb.equals("my field!", "value")

    def test_valid_field_name_with_dot(self):
        result = self.fb.equals("path.depth", 3).build()
        self.assertEqual(result, "path.depth:=3")

    def test_valid_field_name_with_underscore(self):
        result = self.fb.equals("review_state", "published").build()
        self.assertEqual(result, "review_state:=`published`")

    # -- escaping ------------------------------------------------------------

    def test_escape_value_with_spaces(self):
        result = self.fb.equals("Title", "My Document").build()
        self.assertEqual(result, "Title:=`My Document`")

    def test_escape_value_with_special_chars(self):
        result = self.fb.equals("path", "/plone/folder:sub").build()
        self.assertEqual(result, "path:=`/plone/folder:sub`")

    # -- complex composition -------------------------------------------------

    def test_complex_filter(self):
        result = (
            TypesenseFilterBuilder()
            .equals("portal_type", ["Document", "File"])
            .equals("review_state", "published")
            .greater_than("modified", 1700000000)
            .not_equals("Subject", "internal")
            .build()
        )
        self.assertEqual(
            result,
            "portal_type:[`Document`, `File`] && review_state:=`published` "
            "&& modified:>1700000000 && Subject:!=`internal`",
        )


if __name__ == "__main__":
    unittest.main()
