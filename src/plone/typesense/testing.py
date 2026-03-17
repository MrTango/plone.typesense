from plone import api
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.testing import z2

import logging
import os
import plone.typesense
import time
import typesense

log = logging.getLogger(__name__)


MAX_CONNECTION_RETRIES = 20


class PloneTypesenseLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.app.dexterity

        self.loadZCML(package=plone.app.dexterity)
        try:
            import plone.restapi

            self.loadZCML(package=plone.restapi)
        except ImportError:
            pass
        self.loadZCML(package=plone.typesense)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "plone.typesense:default")


class PloneTypesenseRealLayer(PloneSandboxLayer):
    """Testing layer with real Typesense connection.

    Expects Typesense to be running on localhost:8108.
    Start it with: docker run -p 8108:8108 -v/tmp/data:/data typesense/typesense:latest
    """

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        import plone.app.dexterity
        self.loadZCML(package=plone.app.dexterity)
        try:
            import plone.restapi
            self.loadZCML(package=plone.restapi)
        except ImportError:
            pass
        self.loadZCML(package=plone.typesense)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "plone.typesense:default")
        setRoles(portal, TEST_USER_ID, ("Member", "Manager"))

        # Get default config from environment or use defaults
        ts_host = os.environ.get("TYPESENSE_HOST", "localhost")
        ts_port = os.environ.get("TYPESENSE_PORT", "8108")
        ts_protocol = os.environ.get("TYPESENSE_PROTOCOL", "http")
        ts_api_key = os.environ.get("TYPESENSE_API_KEY", "xyz")

        # Configure Typesense settings
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.enabled", True
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.host", ts_host
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.port", ts_port
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.protocol", ts_protocol
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.api_key", ts_api_key
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.collection", "test-content"
        )
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.ts_only_indexes",
            ["Title", "Description", "SearchableText"]
        )

        # Wait for Typesense to be available
        self._wait_for_typesense_service(ts_host, ts_port, ts_protocol, ts_api_key)

    def _wait_for_typesense_service(self, host, port, protocol, api_key):
        """Wait for Typesense service to be available."""
        client = typesense.Client({
            "nodes": [{
                "host": host,
                "port": int(port),
                "protocol": protocol,
            }],
            "api_key": api_key,
            "connection_timeout_seconds": 5,
        })

        counter = 0
        while True:
            if counter == MAX_CONNECTION_RETRIES:
                raise Exception(
                    f"Cannot connect to Typesense service at {protocol}://{host}:{port}. "
                    "Make sure Typesense is running. "
                    "Start with: docker run -p 8108:8108 -v/tmp/typesense-data:/data "
                    "typesense/typesense:latest --data-dir /data --api-key=xyz"
                )
            try:
                if client.operations.is_healthy():
                    log.info(f"Successfully connected to Typesense at {protocol}://{host}:{port}")
                    break
            except Exception as e:
                log.info(f"Waiting for Typesense... (attempt {counter + 1}/{MAX_CONNECTION_RETRIES})")
                time.sleep(1)
                counter += 1


PLONE_TYPESENSE_FIXTURE = PloneTypesenseLayer()


PLONE_TYPESENSE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(PLONE_TYPESENSE_FIXTURE,),
    name="PloneTypesenseLayer:IntegrationTesting",
)


PLONE_TYPESENSE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(PLONE_TYPESENSE_FIXTURE,),
    name="PloneTypesenseLayer:FunctionalTesting",
)


PLONE_TYPESENSE_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        PLONE_TYPESENSE_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="PloneTypesenseLayer:AcceptanceTesting",
)


PLONE_TYPESENSE_REAL_FIXTURE = PloneTypesenseRealLayer()

PLONE_TYPESENSE_REAL_INTEGRATION_TESTING = IntegrationTesting(
    bases=(PLONE_TYPESENSE_REAL_FIXTURE,),
    name="PloneTypesenseRealLayer:IntegrationTesting",
)

PLONE_TYPESENSE_REAL_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(PLONE_TYPESENSE_REAL_FIXTURE,),
    name="PloneTypesenseRealLayer:FunctionalTesting",
)
