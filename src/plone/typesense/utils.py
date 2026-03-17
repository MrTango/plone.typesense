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
    """
    """
    settings = get_settings()
    try:
        indexes = settings.ts_only_indexes
        return set(indexes) if indexes else set()
    except (KeyError, AttributeError):
        return ["Title", "Description", "SearchableText"]


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

