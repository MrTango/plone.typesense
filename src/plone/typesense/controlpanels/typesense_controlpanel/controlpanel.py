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
from plone.typesense import _, log
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
            "fields": [
                {"name": ".*", "type": "auto"},
                {"name": "path", "type": "string", "sort": True},
                {"name": "Title", "type": "string", "infix": True, "optional": True},
                {"name": "sortable_title", "type": "string", "sort": True},
                {"name": "getObjPositionInParent", "type": "int32", "optional": True},
                {"name": "Description", "type": "string", "optional": True},
                {"name": "SearchableText", "type": "string", "infix": True, "optional": True},
                {"name": "portal_type", "type": "string", "facet": True},
                {"name": "Type", "type": "string", "facet": True},
                {"name": "review_state", "type": "string", "facet": True, "optional": True},
                {"name": "Subject", "type": "string[]", "facet": True, "optional": True},
                {"name": "allowedRolesAndUsers", "type": "string[]"},
                {"name": "Date", "type": "int64", "optional": True},
                {"name": "created", "type": "int64", "optional": True},
                {"name": "modified", "type": "int64", "optional": True},
            ],
            "default_sorting_field": "sortable_title",
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
        """clear and rebuild collection from Plone"""
        portal = api.portal.get()
        ts_connector = getUtility(ITypesenseConnector)
        self.objects = []
        batch_size = 100

    @button.buttonAndHandler(_("detect schema changes"), name="detect_schema_changes")
    def handle_detect_schema_changes(self, action):
        """Compare catalog indexes against current Typesense schema and
        report differences."""
        from plone.typesense.mapping import detect_schema_changes

        ts_connector = getUtility(ITypesenseConnector)
        catalog = api.portal.get_tool("portal_catalog")
        messages = IStatusMessage(self.request)

        try:
            ts_client = ts_connector.get_client()
            collection_name = ts_connector.collection_base_name
            current_schema = ts_client.collections[collection_name].retrieve()
        except Exception as e:
            messages.addStatusMessage(
                f"Could not retrieve Typesense schema: {e}", "error"
            )
            self.request.response.redirect(self.request.getURL())
            return

        diff = detect_schema_changes(catalog, current_schema)
        added = diff.get("added", [])
        removed = diff.get("removed", [])
        type_changed = diff.get("type_changed", [])

        if not added and not removed and not type_changed:
            messages.addStatusMessage(
                "Schema is in sync: no differences detected between "
                "catalog indexes and Typesense schema.",
                "info",
            )
        else:
            parts = []
            if added:
                names = ", ".join(f["name"] for f in added)
                parts.append(f"New in catalog (not in Typesense): {names}")
            if removed:
                names = ", ".join(f["name"] for f in removed)
                parts.append(f"In Typesense but not in catalog: {names}")
            if type_changed:
                descs = ", ".join(
                    f"{c['name']} (catalog: {c['catalog_type']}, "
                    f"typesense: {c['typesense_type']})"
                    for c in type_changed
                )
                parts.append(f"Type mismatches: {descs}")

            msg = "Schema differences detected. " + " | ".join(parts)
            messages.addStatusMessage(msg, "warning")
            log.warning("Typesense schema diff: %s", msg)

        self.request.response.redirect(self.request.getURL())

    @button.buttonAndHandler(
        _("generate schema from catalog"), name="generate_schema_from_catalog"
    )
    def handle_generate_schema(self, action):
        """Auto-generate a Typesense schema from the current catalog indexes
        and store it in the control panel ts_schema field."""
        from plone.typesense.mapping import convert_catalog_to_typesense

        catalog = api.portal.get_tool("portal_catalog")
        ts_connector = getUtility(ITypesenseConnector)
        messages = IStatusMessage(self.request)

        try:
            schema = convert_catalog_to_typesense(
                catalog, collection_name=ts_connector.collection_base_name
            )
            api.portal.set_registry_record(
                "plone.typesense.typesense_controlpanel.ts_schema", schema
            )
            messages.addStatusMessage(
                f"Schema generated with {len(schema.get('fields', []))} fields "
                f"and saved to the control panel.",
                "info",
            )
        except Exception as e:
            messages.addStatusMessage(
                f"Error generating schema: {e}", "error"
            )

        self.request.response.redirect(self.request.getURL())



class TypesenseControlpanelFormWrapper(ControlPanelFormWrapper):
    """Custom control panel wrapper with data sync indicator."""

    @property
    def data_sync_status(self):
        """Compare document counts between Plone catalog and Typesense.

        Returns a dict with counts and sync status, or None if unavailable.
        """
        try:
            ts_connector = getUtility(ITypesenseConnector)
            if not ts_connector.enabled:
                return None

            # Get catalog count
            catalog = api.portal.get_tool("portal_catalog")
            catalog_count = len(catalog.unrestrictedSearchResults())

            # Get Typesense count
            ts_client = ts_connector.get_client()
            collection_name = ts_connector.collection_base_name
            collection_info = ts_client.collections[collection_name].retrieve()
            typesense_count = collection_info.get("num_documents", 0)

            in_sync = catalog_count == typesense_count

            return {
                "catalog_count": catalog_count,
                "typesense_count": typesense_count,
                "in_sync": in_sync,
                "difference": abs(catalog_count - typesense_count),
            }
        except Exception as exc:
            log.debug(f"Could not retrieve sync status: {exc}")
            return None

    @property
    def connection_status(self):
        """Check if Typesense connection is healthy."""
        try:
            ts_connector = getUtility(ITypesenseConnector)
            if not ts_connector.enabled:
                return None
            ts_client = ts_connector.get_client()
            return ts_client.operations.is_healthy()
        except Exception:
            return False


TypesenseControlpanelView = layout.wrap_form(
    TypesenseControlpanel, TypesenseControlpanelFormWrapper
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
