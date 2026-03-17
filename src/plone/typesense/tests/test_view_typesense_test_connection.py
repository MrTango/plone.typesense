# -*- coding: utf-8 -*-
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.typesense.testing import PLONE_TYPESENSE_FUNCTIONAL_TESTING
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING
from plone.typesense.views.typesense_test_connection import ITypesenseTestConnection
from zope.component import getMultiAdapter
from zope.interface.interfaces import ComponentLookupError

import unittest


class ViewsIntegrationTest(unittest.TestCase):

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        api.content.create(self.portal, "Folder", "other-folder")
        api.content.create(self.portal, "Document", "front-page")

    def test_typesense_test_connection_is_registered(self):
        view = getMultiAdapter(
            (self.portal["other-folder"], self.portal.REQUEST),
            name="typesense-test-connection",
        )
        self.assertTrue(ITypesenseTestConnection.providedBy(view))

    def test_typesense_test_connection_not_matching_interface(self):
        view_found = True
        try:
            view = getMultiAdapter(
                (self.portal["front-page"], self.portal.REQUEST),
                name="typesense-test-connection",
            )
        except ComponentLookupError:
            view_found = False
        else:
            view_found = ITypesenseTestConnection.providedBy(view)
        self.assertFalse(view_found)


class ViewsFunctionalTest(unittest.TestCase):

    layer = PLONE_TYPESENSE_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
