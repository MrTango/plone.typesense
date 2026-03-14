from plone.typesense import log


def handler(obj, event):
    """Event handler"""
    log.debug(f"{event.__class__} on object {obj.absolute_url()}")
