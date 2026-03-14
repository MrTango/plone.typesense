# -*- coding: utf-8 -*-
import json

from plone import api
from plone.app.registry.browser.controlpanel import (
    ControlPanelFormWrapper,
    RegistryEditForm,
)
from plone.restapi.controlpanels import RegistryConfigletPanel
from plone.z3cform import layout
from Products.statusmessages.interfaces import IStatusMessage
from plone.typesense.global_utilities.typesense import ITypesenseConnector
from zope.component import getUtility
from z3c.form import button
from zope.component import adapter
from zope.component.hooks import getSite
from zope.interface import Interface
from plone.app.z3cform.widget import SingleCheckBoxBoolFieldWidget
from plone import schema
from plone.typesense import _
from plone.typesense.interfaces import IPloneTypesenseLayer
from plone.autoform import directives

class ITypesenseControlpanel(Interface):
    enabled = schema.Bool(
        title=_("Typesense integration enabled"),
        default=True,
        required=False,
    )

    collection = schema.TextLine(
        title=_("Name of Typesense collection"),
        default="content",
        required=True,
    )

    api_key = schema.TextLine(
        title=_("Typesense Admin API key"),
        default="",
        required=True,
    )

    host = schema.TextLine(
        title=_(
            "Typesense Host",
        ),
        description=_(
            "",
        ),
        default="localhost",
        required=False,
        readonly=False,
    )

    port = schema.TextLine(
        title=_(
            "Typesense Port",
        ),
        description=_(
            "",
        ),
        default="8108",
        required=False,
        readonly=False,
    )

    protocol = schema.TextLine(
        title=_(
            "Typesense Protocol",
        ),
        description=_(
            "For Typesense Cloud or other external setups use https!",
        ),
        default="http",
        required=False,
        readonly=False,
    )

    timeout = schema.Int(
        title=_(
            "Typesense connection timeout",
        ),
        description=_(
            "Connection timeout in milliseconds",
        ),
        required=False,
        default=300,
        # defaultFactory=get_default_timeout,
        readonly=False,
    )

    ts_schema = schema.JSONField(
        title=_("Typesense Schema"),
        description=_("Enter a JSON-formatted Typesense schema configuration."),
        schema=json.dumps({}, indent=2),
        default={
            "name": None,
            "fields": [
                {"name": ".*", "type": "auto" },
                {"name": "cmf_uid", "index": False},
                {"name": "path", "type": "string", "sort": True},
                {"name": "Title", "type": "string", "infix": True},
                {"name": "sortable_title", "type": "string", "sort": True},
                {"name": "getObjPositionInParent", "type": "string", "sort": True},
                {"name": "Description", "type": "string"},
                {"name": "SearchableText", "type": "string", "infix": True},
                {"name": "language", "type": "string", "facet": True, "optional": True},
                {"name": "portal_type", "type": "string", "facet": True},
                {"name": "Type", "type": "string", "facet": True},
                {"name": "review_state", "type": "string", "facet": True},
                {"name": "total_comments", "type": "int32", "facet": False, "optional": True},
                {"name": "Subject", "type": "string[]", "facet": True},
                {"name": "allowedRolesAndUsers", "type": "string[]", "facet": False},
                {"name": "Date", "type": "int64", "facet": False},
                {"name": "created", "type": "int64", "facet": False},
                {"name": "modified", "type": "int64", "facet": False},
                {"name": "effective", "type": "int64", "facet": False},
                {"name": "expires", "type": "int64", "facet": False},
            ],
            "default_sorting_field": "sortable_title",
            "token_separators": ["-"],
            "attributesToSnippet": [
                "title",
                "description",
                "text:20",
            ],
            "attributesToHighlight": [
                "title",
                "description",
                "text:20",
            ],
        },
        required=True,
    )

    ts_only_indexes = schema.List(
        title=_(
            u"Typesense only indexes",
        ),
        description=_(
            u"One index name per line.",
        ),
        value_type=schema.TextLine(
            title=u"index",
        ),
        default=["Title", "Description", "SearchableText"],
        required=False,
    )

    directives.widget(highlight=SingleCheckBoxBoolFieldWidget)
    highlight = schema.Bool(
        title=_(
            u'Highlight',
        ),
        description=_(
            u'Enable search result highlighting.',
        ),
        required=False,
        default=False,
        readonly=False,
    )

    highlight_start_tag = schema.TextLine(
        title=_(u'Highlight start tag'),
        description=_(
            u'HTML tag used to wrap the start of highlighted text. '
            u'Default: <mark>'
        ),
        required=False,
        default=u'<mark>',
        readonly=False,
    )

    highlight_end_tag = schema.TextLine(
        title=_(u'Highlight end tag'),
        description=_(
            u'HTML tag used to wrap the end of highlighted text. '
            u'Default: </mark>'
        ),
        required=False,
        default=u'</mark>',
        readonly=False,
    )

    highlight_fields = schema.List(
        title=_(u'Highlight fields'),
        description=_(
            u'Fields to highlight in search results. '
            u'One field name per line. '
            u'Default: Title, Description, SearchableText'
        ),
        value_type=schema.TextLine(title=u'field'),
        default=[u'Title', u'Description', u'SearchableText'],
        required=False,
    )

    bulk_size = schema.Int(
        title=_(
            u'Bulk Size',
        ),
        description=_(
            u'',
        ),
        required=False,
        default=50,
        # defaultFactory=get_default_bulk_size  ,
        readonly=False,
    )


class TypesenseControlpanel(RegistryEditForm):
    schema = ITypesenseControlpanel
    schema_prefix = "plone.typesense.typesense_controlpanel"
    label = _("Typesense Controlpanel")

    @button.buttonAndHandler(_("Save"), name=None)
    def handleSave(self, action):
        self.save()

    def save(self):
        data, errors = self.extractData()

        if errors:
            self.status = self.formErrorsMessage
            return False
        old_collection_name = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.collection"
        )
        old_collection_schema = api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.ts_schema"
        )

        self.applyChanges(data)

        # if collection name changed, initialize new collection
        # TODO migrate collection data
        ts_connector = getUtility(ITypesenseConnector)
        if old_collection_name != data.get("collection"):
            ts_connector.init_collection()
        elif old_collection_schema != data.get("ts_schema"):
            ts_connector.clear()
        return True

    @button.buttonAndHandler(_("Cancel"), name="cancel")
    def handleCancel(self, action):
        super().handleCancel(self, action)

    @button.buttonAndHandler(_("test connection"), name="test_connection")
    def handle_test_connection(self, action):
        """call typesense test connection view
        """
        ts_connector = getUtility(ITypesenseConnector)
        ts_client = ts_connector.get_client()
        status = ""
        try:
            healthy = ts_client.operations.is_healthy()
            if healthy:
                status = "Connection success, Typesense is healthy."
        except Exception as e:
            status = f"Typesense error:\n{e}"

        IStatusMessage(self.request).addStatusMessage(status, "info")
        self.request.response.redirect(self.request.getURL())

    @button.buttonAndHandler(_("clear and rebuild"), name="clear_and_rebuild")
    def handle_clear_and_rebuild(self, action):
        """ clear and rebuild collection from Plone
        """
        portal = api.portal.get()
        ts_connector = getUtility(ITypesenseConnector)
        # ts_client = ts_connector.get_client()
        self.objects = []
        batch_size = 100

        # def _index_object(obj, path):
        #     if not ICatalogAware.providedBy(obj):
        #         return
        #     self.objects.append(obj)
        #     if len(self.objects) >= batch_size:
        #         ts_connector.index(self.objects)
        #         self.objects = []
        #     if len(self.objects) > 0:
        #         ts_connector.index(self.objects)

        # portal.ZopeFindAndApply(portal, search_sub=True, apply_func=_index_object)
        # return self.index()



TypesenseControlpanelView = layout.wrap_form(
    TypesenseControlpanel, ControlPanelFormWrapper
)


@adapter(Interface, IPloneTypesenseLayer)
class TypesenseControlpanelConfigletPanel(RegistryConfigletPanel):
    """Control Panel endpoint"""

    schema = ITypesenseControlpanel
    configlet_id = "typesense_controlpanel-controlpanel"
    configlet_category_id = "Products"
    title = _("Typesense Controlpanel")
    group = ""
    schema_prefix = "plone.typesense.typesense_controlpanel"
