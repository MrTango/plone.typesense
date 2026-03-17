# -*- coding: utf-8 -*-
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.typesense.testing import PLONE_TYPESENSE_FUNCTIONAL_TESTING
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING

import unittest


class SubscriberIntegrationTest(unittest.TestCase):

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])


class SubscriberFunctionalTest(unittest.TestCase):

    layer = PLONE_TYPESENSE_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
