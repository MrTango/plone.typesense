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


TS_ONLY_INDEXES_DEFAULT = {"Title", "Description", "SearchableText"}


def get_ts_only_indexes():
    """Return the set of index names that should only be stored in Typesense."""
    settings = get_settings()
    try:
        indexes = settings.ts_only_indexes
        return set(indexes) if indexes else TS_ONLY_INDEXES_DEFAULT
    except (KeyError, AttributeError):
        return TS_ONLY_INDEXES_DEFAULT


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

