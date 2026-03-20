"""Tests for Typesense schema validation."""

import json
import unittest

from plone.typesense.global_utilities.typesense import TypesenseConnector
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING


class TestDefaultSchemaFields(unittest.TestCase):
    """Verify that the default ts_schema shipped with the control panel is valid."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        from plone import api

        self.portal = self.layer["portal"]
        self.schema = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.ts_schema"
        )

    def test_all_fields_have_name(self):
        for field in self.schema["fields"]:
            self.assertIn("name", field, f"Field missing 'name': {field}")

    def test_all_fields_have_type(self):
        for field in self.schema["fields"]:
            self.assertIn(
                "type",
                field,
                f"Field '{field.get('name', '?')}' is missing required 'type' key",
            )


class TestSanitizeSchemaFields(unittest.TestCase):
    """Test _sanitize_schema_fields defensive validation."""

    def setUp(self):
        self.connector = TypesenseConnector()

    def test_adds_type_auto_when_missing(self):
        schema = {
            "fields": [
                {"name": "cmf_uid", "index": False},
            ]
        }
        self.connector._sanitize_schema_fields(schema)
        self.assertEqual(schema["fields"][0]["type"], "auto")

    def test_preserves_existing_type(self):
        schema = {
            "fields": [
                {"name": "Title", "type": "string", "infix": True},
            ]
        }
        self.connector._sanitize_schema_fields(schema)
        self.assertEqual(schema["fields"][0]["type"], "string")

    def test_handles_empty_fields(self):
        schema = {"fields": []}
        self.connector._sanitize_schema_fields(schema)
        self.assertEqual(schema["fields"], [])

    def test_handles_no_fields_key(self):
        schema = {}
        self.connector._sanitize_schema_fields(schema)
        self.assertEqual(schema, {})

    def test_multiple_fields_mixed(self):
        schema = {
            "fields": [
                {"name": ".*", "type": "auto"},
                {"name": "cmf_uid", "index": False},
                {"name": "path", "type": "string", "sort": True},
                {"name": "other_missing"},
            ]
        }
        self.connector._sanitize_schema_fields(schema)
        self.assertEqual(schema["fields"][0]["type"], "auto")
        self.assertEqual(schema["fields"][1]["type"], "auto")
        self.assertEqual(schema["fields"][2]["type"], "string")
        self.assertEqual(schema["fields"][3]["type"], "auto")
