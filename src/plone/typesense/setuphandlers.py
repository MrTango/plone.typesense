from Products.CMFPlone.interfaces import INonInstallable
from zope.interface import implementer

from plone.typesense import log


@implementer(INonInstallable)
class HiddenProfiles(object):
    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            "plone.typesense:uninstall",
        ]

    def getNonInstallableProducts(self):
        """Hide the upgrades package from site-creation and quickinstaller."""
        return ["plone.typesense.upgrades"]


def _get_connector():
    """Get the Typesense connector utility.

    Returns None if the utility is not available.
    """
    from zope.component import queryUtility

    from plone.typesense.global_utilities.typesense import ITypesenseConnector

    return queryUtility(ITypesenseConnector)


def post_install(context):
    """Post install script.

    Initialize the Typesense collection on first install.
    """
    connector = _get_connector()
    if connector is None:
        log.warning(
            "Typesense connector utility not found. "
            "Collection will be initialized when the connector is available."
        )
        return

    if not connector.enabled:
        log.info(
            "Typesense integration is not enabled. "
            "Collection will be initialized when enabled via the control panel."
        )
        return

    try:
        connector.test_connection()
    except Exception as exc:
        log.warning(
            "Could not connect to Typesense during install: %s. "
            "Collection will need to be initialized manually.",
            exc,
        )
        return

    try:
        connector.init_collection()
        log.info("Typesense collection initialized successfully during install.")
    except Exception as exc:
        log.warning(
            "Could not initialize Typesense collection during install: %s. "
            "Collection will need to be initialized manually.",
            exc,
        )


def uninstall(context):
    """Uninstall script.

    Clean up the Typesense collection on uninstall.
    """
    connector = _get_connector()
    if connector is None:
        log.warning(
            "Typesense connector utility not found. "
            "No collection cleanup performed."
        )
        return

    if not connector.enabled:
        log.info(
            "Typesense integration is not enabled. "
            "No collection cleanup performed."
        )
        return

    try:
        connector.test_connection()
    except Exception as exc:
        log.warning(
            "Could not connect to Typesense during uninstall: %s. "
            "Collection cleanup skipped.",
            exc,
        )
        return

    try:
        ts = connector.get_client()
        collection_name = connector.collection_base_name
        if collection_name:
            # Try to delete the aliased collection
            try:
                alias = ts.aliases[collection_name].retrieve()
                if "collection_name" in alias:
                    aliased_name = alias["collection_name"]
                    log.info(
                        "Deleting aliased collection '%s'.", aliased_name
                    )
                    ts.collections[aliased_name].delete()
                # Delete the alias itself
                log.info("Deleting alias '%s'.", collection_name)
                ts.aliases[collection_name].delete()
            except Exception:
                # If no alias exists, try deleting the collection directly
                try:
                    log.info(
                        "Deleting collection '%s'.", collection_name
                    )
                    ts.collections[collection_name].delete()
                except Exception as exc:
                    log.warning(
                        "Could not delete collection '%s': %s",
                        collection_name,
                        exc,
                    )
        log.info("Typesense collection cleanup completed during uninstall.")
    except Exception as exc:
        log.warning(
            "Error during Typesense collection cleanup: %s. "
            "Manual cleanup may be required.",
            exc,
        )
