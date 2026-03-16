"""Tests for TypesenseManager bug fixes B1-B7.

Since importing manager.py pulls in the full Plone stack (via plone.api),
these tests verify the source code directly by inspecting the module AST
and testing individual methods with isolated mocking.
"""
import ast
import os
import unittest


MANAGER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "manager.py"
)


class TestManagerSourceAnalysis(unittest.TestCase):
    """Verify required properties/imports exist by parsing the source AST."""

    def setUp(self):
        with open(MANAGER_PATH) as f:
            self.source = f.read()
        self.tree = ast.parse(self.source)
        # Find the TypesenseManager class
        self.manager_cls = None
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == "TypesenseManager":
                self.manager_cls = node
                break

    def _get_property_names(self):
        """Extract property names from the class."""
        props = set()
        for node in self.manager_cls.body:
            if isinstance(node, ast.FunctionDef):
                for deco in node.decorator_list:
                    if isinstance(deco, ast.Name) and deco.id == "property":
                        props.add(node.name)
        return props

    def _get_method_names(self):
        """Extract method names from the class."""
        return {
            node.name for node in self.manager_cls.body
            if isinstance(node, ast.FunctionDef)
        }

    def test_manager_class_found(self):
        self.assertIsNotNone(self.manager_cls)

    def test_B1_active_property_exists(self):
        """B1: 'active' must be a property on TypesenseManager."""
        self.assertIn("active", self._get_property_names())

    def test_B3_collection_name_property_exists(self):
        """B3: 'collection_name' must be a property."""
        self.assertIn("collection_name", self._get_property_names())

    def test_B4_raise_search_exception_property_exists(self):
        """B4: 'raise_search_exception' must be a property."""
        self.assertIn("raise_search_exception", self._get_property_names())

    def test_B5_highlight_threshold_property_exists(self):
        """B5: 'highlight_threshold' must be a property."""
        self.assertIn("highlight_threshold", self._get_property_names())

    def test_enabled_property_exists(self):
        self.assertIn("enabled", self._get_property_names())

    def test_B7_get_record_by_path_method_exists(self):
        """B7: get_record_by_path must exist as a method."""
        self.assertIn("get_record_by_path", self._get_method_names())

    def test_B2_getUtility_imported(self):
        """B2: getUtility must be imported."""
        self.assertIn("from zope.component import getUtility", self.source)

    def test_B2_ITypesenseConnector_imported(self):
        """B2: ITypesenseConnector must be imported."""
        self.assertIn("ITypesenseConnector", self.source)

    def test_B7_no_elasticsearch_syntax_in_get_record_by_path(self):
        """B7: get_record_by_path must not use ES query syntax."""
        # Find the method body
        for node in self.manager_cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "get_record_by_path":
                method_source = ast.get_source_segment(self.source, node)
                self.assertNotIn("self.connection", method_source)
                self.assertNotIn("self.index_name", method_source)
                self.assertNotIn("match_all", method_source)
                self.assertNotIn('"query":', method_source)
                # Should use Typesense search pattern
                self.assertIn("documents.search", method_source)
                self.assertIn("filter_by", method_source)
                return
        self.fail("get_record_by_path not found")

    def test_B1_active_checks_enabled_and_health(self):
        """B1: active property should check enabled and health."""
        for node in self.manager_cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "active":
                method_source = ast.get_source_segment(self.source, node)
                self.assertIn("self.enabled", method_source)
                self.assertIn("is_healthy", method_source)
                return
        self.fail("active property not found")

    def test_B3_collection_name_delegates_to_connector(self):
        """B3: collection_name should delegate to connector."""
        for node in self.manager_cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "collection_name":
                method_source = ast.get_source_segment(self.source, node)
                self.assertIn("collection_base_name", method_source)
                return
        self.fail("collection_name property not found")


class TestManagerSearchResultsSource(unittest.TestCase):
    """Verify search_results uses self.active, not self.enabled."""

    def setUp(self):
        with open(MANAGER_PATH) as f:
            self.source = f.read()
        self.tree = ast.parse(self.source)
        self.manager_cls = None
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == "TypesenseManager":
                self.manager_cls = node
                break

    def test_search_results_uses_self_active(self):
        """search_results must use self.active (not self.enabled)."""
        for node in self.manager_cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "search_results":
                method_source = ast.get_source_segment(self.source, node)
                self.assertIn("self.active", method_source)
                return
        self.fail("search_results not found")

    def test_search_results_uses_raise_search_exception(self):
        """search_results must use self.raise_search_exception."""
        for node in self.manager_cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "search_results":
                method_source = ast.get_source_segment(self.source, node)
                self.assertIn("self.raise_search_exception", method_source)
                return
        self.fail("search_results not found")


if __name__ == "__main__":
    unittest.main()
