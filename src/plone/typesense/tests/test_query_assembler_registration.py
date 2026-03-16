"""Tests for B6: Correct QueryAssembler registration."""
import unittest

from plone.typesense.interfaces import IQueryAssembler
from plone.typesense.query import TypesenseQueryAssembler


class TestQueryAssemblerInterface(unittest.TestCase):
    """Verify TypesenseQueryAssembler implements IQueryAssembler."""

    def test_typesense_assembler_implements_interface(self):
        """TypesenseQueryAssembler must declare it implements IQueryAssembler."""
        self.assertTrue(
            IQueryAssembler.implementedBy(TypesenseQueryAssembler),
            "TypesenseQueryAssembler must implement IQueryAssembler",
        )

    def test_zcml_registers_typesense_assembler(self):
        """ZCML must register TypesenseQueryAssembler, not the ES-style one."""
        # We verify this by parsing the ZCML file
        import os
        zcml_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "configure.zcml",
        )
        with open(zcml_path) as f:
            content = f.read()

        self.assertIn(
            '.query.TypesenseQueryAssembler',
            content,
            "configure.zcml must register TypesenseQueryAssembler",
        )
        # The ES-style QueryAssembler should NOT be the registered factory
        self.assertNotIn(
            'factory=".query.QueryAssembler"',
            content,
            "configure.zcml must NOT register the ES-style QueryAssembler",
        )

    def test_typesense_assembler_has_normalize(self):
        """TypesenseQueryAssembler must have normalize method."""
        self.assertTrue(hasattr(TypesenseQueryAssembler, 'normalize'))

    def test_typesense_assembler_is_callable(self):
        """TypesenseQueryAssembler must be callable (__call__)."""
        self.assertTrue(hasattr(TypesenseQueryAssembler, '__call__'))


if __name__ == "__main__":
    unittest.main()
