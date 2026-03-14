"""Tests for scoped search key generation."""

import base64
import json
import unittest
from unittest.mock import MagicMock, patch

from plone.typesense.scoped_search import (
    _generate_scoped_key,
    build_filter_by,
)


class TestBuildFilterBy(unittest.TestCase):
    """Test filter_by string generation."""

    def test_single_role(self):
        result = build_filter_by(["Anonymous"])
        self.assertEqual(result, "allowedRolesAndUsers:=[`Anonymous`]")

    def test_multiple_roles(self):
        result = build_filter_by(["Anonymous", "Member", "user:admin"])
        self.assertEqual(
            result,
            "allowedRolesAndUsers:=[`Anonymous`, `Member`, `user:admin`]"
        )

    def test_empty_list(self):
        result = build_filter_by([])
        self.assertEqual(result, "allowedRolesAndUsers:=[]")

    def test_backtick_escaping(self):
        result = build_filter_by(["role`with`backticks"])
        self.assertIn("\\`", result)

    def test_typical_plone_roles(self):
        roles = [
            "Anonymous",
            "Authenticated",
            "Member",
            "user:john",
        ]
        result = build_filter_by(roles)
        self.assertIn("`Anonymous`", result)
        self.assertIn("`Authenticated`", result)
        self.assertIn("`Member`", result)
        self.assertIn("`user:john`", result)


class TestGenerateScopedKey(unittest.TestCase):
    """Test scoped key generation."""

    def test_generates_base64_key(self):
        key = _generate_scoped_key(
            "test-search-key-12345",
            {"filter_by": "allowedRolesAndUsers:=[`Anonymous`]", "collection": "content"},
        )
        # Result should be valid base64
        decoded = base64.b64decode(key)
        self.assertIsInstance(decoded, bytes)

    def test_key_contains_params(self):
        params = {
            "filter_by": "allowedRolesAndUsers:=[`Anonymous`]",
            "collection": "content",
        }
        key = _generate_scoped_key("test-search-key-12345", params)
        decoded = base64.b64decode(key).decode("utf-8")
        # The decoded key should contain the JSON params
        self.assertIn("allowedRolesAndUsers", decoded)
        self.assertIn("content", decoded)

    def test_different_keys_produce_different_results(self):
        params = {"filter_by": "allowedRolesAndUsers:=[`Anonymous`]"}
        key1 = _generate_scoped_key("key-aaaa-1111", params)
        key2 = _generate_scoped_key("key-bbbb-2222", params)
        self.assertNotEqual(key1, key2)

    def test_different_params_produce_different_results(self):
        key = "test-search-key-12345"
        key1 = _generate_scoped_key(key, {"filter_by": "allowedRolesAndUsers:=[`Anonymous`]"})
        key2 = _generate_scoped_key(key, {"filter_by": "allowedRolesAndUsers:=[`Member`]"})
        self.assertNotEqual(key1, key2)

    def test_deterministic(self):
        key = "test-search-key-12345"
        params = {"filter_by": "allowedRolesAndUsers:=[`Anonymous`]"}
        key1 = _generate_scoped_key(key, params)
        key2 = _generate_scoped_key(key, params)
        self.assertEqual(key1, key2)

    def test_returns_string(self):
        key = _generate_scoped_key(
            "test-search-key-12345",
            {"filter_by": "test"},
        )
        self.assertIsInstance(key, str)

    def test_key_prefix_embedded(self):
        search_key = "abcd-search-key"
        key = _generate_scoped_key(search_key, {"filter_by": "test"})
        decoded = base64.b64decode(key).decode("utf-8")
        # The first 4 chars of the search key should appear after the HMAC digest
        self.assertIn("abcd", decoded)


class TestGenerateScopedSearchKey(unittest.TestCase):
    """Test the full generate_scoped_search_key function (requires Plone mocking)."""

    @patch("plone.typesense.scoped_search.get_allowed_roles_and_users")
    def test_generates_key_with_user_roles(self, mock_get_roles):
        from plone.typesense.scoped_search import generate_scoped_search_key

        mock_get_roles.return_value = ["Anonymous", "Member", "user:testuser"]

        key = generate_scoped_search_key("search-key-12345", "my_collection")

        self.assertIsInstance(key, str)
        mock_get_roles.assert_called_once()

        # Verify the embedded params
        decoded = base64.b64decode(key).decode("utf-8")
        self.assertIn("allowedRolesAndUsers", decoded)
        self.assertIn("my_collection", decoded)

    @patch("plone.typesense.scoped_search.get_allowed_roles_and_users")
    def test_raises_without_search_key(self, mock_get_roles):
        from plone.typesense.scoped_search import generate_scoped_search_key

        with self.assertRaises(ValueError):
            generate_scoped_search_key("", "my_collection")

        with self.assertRaises(ValueError):
            generate_scoped_search_key(None, "my_collection")

    @patch("plone.typesense.scoped_search.get_allowed_roles_and_users")
    def test_passes_user_to_get_roles(self, mock_get_roles):
        from plone.typesense.scoped_search import generate_scoped_search_key

        mock_get_roles.return_value = ["Anonymous"]
        mock_user = MagicMock()

        generate_scoped_search_key("search-key-12345", "collection", user=mock_user)

        mock_get_roles.assert_called_once_with(mock_user)


if __name__ == "__main__":
    unittest.main()
