# -*- coding: utf-8 -*-

# from plone.typesense import _
# from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.interfaces import ICatalogAware
from Products.Five.browser import BrowserView
from zope.component import getUtility
from zope.interface import Interface, implementer

from plone import api
from plone.typesense import log
from plone.typesense.global_utilities.typesense import ITypesenseConnector


class ITypesenseReindexCollection(Interface):
    """Marker Interface for ITypesenseReindexCollection"""


@implementer(ITypesenseReindexCollection)
class TypesenseReindexCollection(BrowserView):

    def __call__(self):
        portal = api.portal.get()
        ts_connector = getUtility(ITypesenseConnector)
        # ts_client = ts_connector.get_client()
        self.objects = []
        batch_size = 100

        def _index_object(obj, path):
            if not ICatalogAware.providedBy(obj):
                return
            self.objects.append(obj)
            if len(self.objects) >= batch_size:
                ts_connector.index(self.objects)
                self.objects = []
            if len(self.objects) > 0:
                ts_connector.index(self.objects)

        portal.ZopeFindAndApply(portal, search_sub=True, apply_func=_index_object)
        return self.index()
