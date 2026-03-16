# -*- coding: utf-8 -*-
"""Tests for connection resilience: multi-node, retries, env-var API key fallback."""
import os
import unittest
from unittest import mock

from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING


class TestEnvVarApiKeyFallback(unittest.TestCase):
    """Test that the API key can be loaded from environment variable."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_connector(self):
        from plone.typesense.global_utilities.typesense import ITypesenseConnector
        from zope.component import getUtility

        return getUtility(ITypesenseConnector)

    def test_api_key_from_registry(self):
        """When registry has an API key, it should be used."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", "registry-key-123"
        )
        connector = self._get_connector()
        self.assertEqual(connector.get_api_key, "registry-key-123")

    def test_api_key_from_env_when_registry_empty(self):
        """When registry API key is empty, fall back to TYPESENSE_API_KEY env var."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", ""
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_API_KEY": "env-key-456"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_api_key, "env-key-456")

    def test_api_key_none_when_both_missing(self):
        """When both registry and env var are empty, return None."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", ""
        )
        with mock.patch.dict(os.environ, {}, clear=False):
            # Ensure TYPESENSE_API_KEY is not set
            env = os.environ.copy()
            env.pop("TYPESENSE_API_KEY", None)
            with mock.patch.dict(os.environ, env, clear=True):
                connector = self._get_connector()
                self.assertIsNone(connector.get_api_key)

    def test_registry_key_takes_precedence_over_env(self):
        """Registry key should take precedence over env var when both are set."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", "registry-key"
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_API_KEY": "env-key"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_api_key, "registry-key")


class TestEnvVarHostFallback(unittest.TestCase):
    """Test that host can be loaded from environment variable."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_connector(self):
        from plone.typesense.global_utilities.typesense import ITypesenseConnector
        from zope.component import getUtility

        return getUtility(ITypesenseConnector)

    def test_host_from_registry(self):
        """When registry has a host, it should be used."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.host", "registry-host"
        )
        connector = self._get_connector()
        self.assertEqual(connector.get_host, "registry-host")

    def test_host_from_env_when_registry_empty(self):
        """When registry host is empty, fall back to TYPESENSE_HOST env var."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.host", ""
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_HOST": "docker-host"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_host, "docker-host")

    def test_host_defaults_to_localhost(self):
        """When both registry and env var are empty, default to localhost."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.host", ""
        )
        env = os.environ.copy()
        env.pop("TYPESENSE_HOST", None)
        with mock.patch.dict(os.environ, env, clear=True):
            connector = self._get_connector()
            self.assertEqual(connector.get_host, "localhost")

    def test_registry_host_takes_precedence_over_env(self):
        """Registry host should take precedence over env var."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.host", "registry-host"
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_HOST": "env-host"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_host, "registry-host")


class TestEnvVarPortFallback(unittest.TestCase):
    """Test that port can be loaded from environment variable."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_connector(self):
        from plone.typesense.global_utilities.typesense import ITypesenseConnector
        from zope.component import getUtility

        return getUtility(ITypesenseConnector)

    def test_port_from_registry(self):
        """When registry has a port, it should be used."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.port", "9108"
        )
        connector = self._get_connector()
        self.assertEqual(connector.get_port, "9108")

    def test_port_from_env_when_registry_empty(self):
        """When registry port is empty, fall back to TYPESENSE_PORT env var."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.port", ""
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_PORT": "443"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_port, "443")

    def test_port_defaults_to_8108(self):
        """When both registry and env var are empty, default to 8108."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.port", ""
        )
        env = os.environ.copy()
        env.pop("TYPESENSE_PORT", None)
        with mock.patch.dict(os.environ, env, clear=True):
            connector = self._get_connector()
            self.assertEqual(connector.get_port, "8108")

    def test_registry_port_takes_precedence_over_env(self):
        """Registry port should take precedence over env var."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.port", "9108"
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_PORT": "443"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_port, "9108")


class TestEnvVarProtocolFallback(unittest.TestCase):
    """Test that protocol can be loaded from environment variable."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_connector(self):
        from plone.typesense.global_utilities.typesense import ITypesenseConnector
        from zope.component import getUtility

        return getUtility(ITypesenseConnector)

    def test_protocol_from_registry(self):
        """When registry has a protocol, it should be used."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.protocol", "https"
        )
        connector = self._get_connector()
        self.assertEqual(connector.get_protocol, "https")

    def test_protocol_from_env_when_registry_empty(self):
        """When registry protocol is empty, fall back to TYPESENSE_PROTOCOL env var."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.protocol", ""
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_PROTOCOL": "https"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_protocol, "https")

    def test_protocol_defaults_to_http(self):
        """When both registry and env var are empty, default to http."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.protocol", ""
        )
        env = os.environ.copy()
        env.pop("TYPESENSE_PROTOCOL", None)
        with mock.patch.dict(os.environ, env, clear=True):
            connector = self._get_connector()
            self.assertEqual(connector.get_protocol, "http")

    def test_registry_protocol_takes_precedence_over_env(self):
        """Registry protocol should take precedence over env var."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.protocol", "https"
        )
        with mock.patch.dict(os.environ, {"TYPESENSE_PROTOCOL": "http"}):
            connector = self._get_connector()
            self.assertEqual(connector.get_protocol, "https")


class TestMultiNodeSupport(unittest.TestCase):
    """Test multi-node configuration parsing."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_connector(self):
        from plone.typesense.global_utilities.typesense import ITypesenseConnector
        from zope.component import getUtility

        return getUtility(ITypesenseConnector)

    def test_parse_additional_nodes_empty(self):
        """Empty additional nodes should return empty list."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes", ""
        )
        connector = self._get_connector()
        self.assertEqual(connector._parse_additional_nodes(), [])

    def test_parse_additional_nodes_single(self):
        """Single additional node should be parsed correctly."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes",
            "node2.example.com:8108:http",
        )
        connector = self._get_connector()
        nodes = connector._parse_additional_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["host"], "node2.example.com")
        self.assertEqual(nodes[0]["port"], 8108)
        self.assertEqual(nodes[0]["protocol"], "http")

    def test_parse_additional_nodes_multiple(self):
        """Multiple additional nodes should all be parsed."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes",
            "node2.example.com:8108:http\nnode3.example.com:443:https",
        )
        connector = self._get_connector()
        nodes = connector._parse_additional_nodes()
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]["host"], "node2.example.com")
        self.assertEqual(nodes[1]["host"], "node3.example.com")
        self.assertEqual(nodes[1]["port"], 443)
        self.assertEqual(nodes[1]["protocol"], "https")

    def test_parse_additional_nodes_skips_invalid(self):
        """Invalid lines should be skipped with a warning."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes",
            "valid-node:8108:http\ninvalid-line\nalso:invalid",
        )
        connector = self._get_connector()
        nodes = connector._parse_additional_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["host"], "valid-node")

    def test_parse_additional_nodes_skips_invalid_port(self):
        """Lines with non-numeric port should be skipped."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes",
            "node1:abc:http",
        )
        connector = self._get_connector()
        nodes = connector._parse_additional_nodes()
        self.assertEqual(len(nodes), 0)

    def test_parse_additional_nodes_handles_blank_lines(self):
        """Blank lines should be ignored."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes",
            "\nnode2:8108:http\n\n",
        )
        connector = self._get_connector()
        nodes = connector._parse_additional_nodes()
        self.assertEqual(len(nodes), 1)

    def test_get_client_includes_all_nodes(self):
        """get_client should create a client with primary + additional nodes."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", "test-key"
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.host", "primary.example.com"
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.port", "8108"
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.protocol", "http"
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes",
            "secondary.example.com:443:https",
        )
        connector = self._get_connector()
        # Reset cached client
        connector.data.client = None

        with mock.patch("typesense.Client") as mock_client:
            connector.get_client()
            call_args = mock_client.call_args[0][0]
            nodes = call_args["nodes"]
            self.assertEqual(len(nodes), 2)
            self.assertEqual(nodes[0]["host"], "primary.example.com")
            self.assertEqual(nodes[1]["host"], "secondary.example.com")
            self.assertEqual(nodes[1]["port"], 443)
            self.assertEqual(nodes[1]["protocol"], "https")


class TestRetryConfiguration(unittest.TestCase):
    """Test that retry/resilience settings are passed to the Typesense client."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_connector(self):
        from plone.typesense.global_utilities.typesense import ITypesenseConnector
        from zope.component import getUtility

        return getUtility(ITypesenseConnector)

    def test_default_retry_settings(self):
        """Default retry settings should be available."""
        connector = self._get_connector()
        self.assertEqual(connector.get_num_retries, 3)
        self.assertEqual(connector.get_retry_interval_seconds, 1.0)
        self.assertEqual(connector.get_healthcheck_interval_seconds, 60)

    def test_retry_settings_passed_to_client(self):
        """Retry settings should be passed to the Typesense client constructor."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", "test-key"
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.num_retries", 5
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.retry_interval_seconds", 2.0
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.healthcheck_interval_seconds", 30
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.timeout", 15
        )
        connector = self._get_connector()
        # Reset cached client
        connector.data.client = None

        with mock.patch("typesense.Client") as mock_client:
            connector.get_client()
            call_args = mock_client.call_args[0][0]
            self.assertEqual(call_args["num_retries"], 5)
            self.assertEqual(call_args["retry_interval_seconds"], 2.0)
            self.assertEqual(call_args["healthcheck_interval_seconds"], 30)
            self.assertEqual(call_args["connection_timeout_seconds"], 15)

    def test_client_config_with_env_api_key(self):
        """Client should work with env var API key and retry settings."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", ""
        )
        connector = self._get_connector()
        connector.data.client = None

        with mock.patch.dict(os.environ, {"TYPESENSE_API_KEY": "env-key-789"}):
            with mock.patch("typesense.Client") as mock_client:
                connector.get_client()
                call_args = mock_client.call_args[0][0]
                self.assertEqual(call_args["api_key"], "env-key-789")
                self.assertIn("num_retries", call_args)
                self.assertIn("retry_interval_seconds", call_args)
                self.assertIn("healthcheck_interval_seconds", call_args)


class TestControlPanelFields(unittest.TestCase):
    """Test that new control panel fields are registered properly."""

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_additional_nodes_field_exists(self):
        """The additional_nodes registry record should exist."""
        value = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.additional_nodes"
        )
        self.assertEqual(value, "")

    def test_num_retries_field_exists(self):
        """The num_retries registry record should exist."""
        value = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.num_retries"
        )
        self.assertEqual(value, 3)

    def test_retry_interval_field_exists(self):
        """The retry_interval_seconds registry record should exist."""
        value = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.retry_interval_seconds"
        )
        self.assertEqual(value, 1.0)

    def test_healthcheck_interval_field_exists(self):
        """The healthcheck_interval_seconds registry record should exist."""
        value = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.healthcheck_interval_seconds"
        )
        self.assertEqual(value, 60)

    def test_timeout_default_updated(self):
        """The timeout default should be 10 (seconds, not milliseconds)."""
        value = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.timeout"
        )
        self.assertEqual(value, 10)
