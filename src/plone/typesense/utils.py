from plone.registry.interfaces import IRegistry
from Products.ZCatalog import ZCatalog
from Products.ZCatalog.CatalogBrains import AbstractCatalogBrain
from zope.component import getUtility
from plone.typesense import log
from plone.typesense.controlpanels.typesense_controlpanel.controlpanel import (
    ITypesenseControlpanel,
)


def get_settings():
    """Return ITypesenseControlpanel values."""
    registry = getUtility(IRegistry)
    try:
        settings = registry.forInterface(ITypesenseControlpanel, check=False)
    except Exception:  # noQA
        settings = None
    return settings


def get_ts_only_indexes():
    """Get the list of indexes that should only be queried via Typesense.

    Returns a set of index names.
    """
    settings = get_settings()
    try:
        indexes = settings.ts_only_indexes
        # Use default if not configured
        if not indexes:
            indexes = ["Title", "Description", "SearchableText"]
        return set(indexes)
    except (KeyError, AttributeError):
        # Fallback to defaults
        return set(["Title", "Description", "SearchableText"])


def get_brain_from_path(zcatalog: ZCatalog, path: str) -> AbstractCatalogBrain:
    rid = zcatalog.uids.get(path)
    if isinstance(rid, int):
        try:
            return zcatalog[rid]
        except KeyError:
            log.error(f"Couldn't get catalog entry for path: {path}")
    else:
        log.error(f"Got a key for path that is not integer: {path}")
    return None

