"""View to return a scoped search API key for the current user."""

import json

from Products.Five.browser import BrowserView
from zope.component import getUtility
from zope.interface import Interface, implementer

from plone import api
from plone.typesense import log
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from plone.typesense.scoped_search import generate_scoped_search_key


class IScopedSearchKeyView(Interface):
    """Marker Interface for IScopedSearchKeyView"""


@implementer(IScopedSearchKeyView)
class ScopedSearchKeyView(BrowserView):
    """Return a scoped Typesense search key for the current user.

    The scoped key embeds the user's allowedRolesAndUsers as a filter,
    so the user can only search for documents they have permission to see.

    Returns JSON: {"key": "<scoped_key>", "collection": "<name>"}
    """

    def __call__(self):
        self.request.response.setHeader("Content-Type", "application/json")

        try:
            search_api_key = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.search_api_key"
            )
        except api.exc.InvalidParameterError:
            search_api_key = None

        if not search_api_key:
            self.request.response.setStatus(503)
            return json.dumps(
                {"error": "Scoped search keys are not configured. "
                 "Set a search-only API key in the Typesense control panel."}
            )

        try:
            collection_name = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.collection"
            )
        except api.exc.InvalidParameterError:
            self.request.response.setStatus(503)
            return json.dumps(
                {"error": "No Typesense collection configured."}
            )

        try:
            scoped_key = generate_scoped_search_key(
                search_api_key, collection_name
            )
        except Exception as e:
            log.error(f"Failed to generate scoped search key: {e}")
            self.request.response.setStatus(500)
            return json.dumps({"error": "Failed to generate scoped search key."})

        return json.dumps({
            "key": scoped_key,
            "collection": collection_name,
        })
