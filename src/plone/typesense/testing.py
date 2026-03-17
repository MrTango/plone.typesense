# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import plone.typesense


class PloneTypesenseLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.app.dexterity

        self.loadZCML(package=plone.app.dexterity)
        import plone.restapi

        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=plone.typesense)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "plone.typesense:default")


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
