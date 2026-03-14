"""Scoped search API key generation for Typesense.

Generates per-user scoped search keys that embed the user's
allowedRolesAndUsers as a filter_by parameter. This allows
client-side search without exposing the admin API key.
"""

import base64
import hashlib
import hmac
import json

from plone import api
from plone.typesense import log


def get_allowed_roles_and_users(user=None):
    """Get the allowedRolesAndUsers index values for a user.

    This mirrors what CatalogTool._listAllowedRolesAndUsers returns.
    """
    catalog = api.portal.get_tool("portal_catalog")
    if user is None:
        user = api.user.get_current()
    return catalog._listAllowedRolesAndUsers(user)


def build_filter_by(allowed_roles_and_users):
    """Build a Typesense filter_by string from allowedRolesAndUsers.

    :param allowed_roles_and_users: list of role/user strings
    :returns: filter_by string for Typesense
    """
    escaped = []
    for value in allowed_roles_and_users:
        # Escape backticks in values for Typesense
        escaped.append(value.replace("`", "\\`"))
    values_str = ", ".join(f"`{v}`" for v in escaped)
    return f"allowedRolesAndUsers:=[{values_str}]"


def _generate_scoped_key(search_api_key, params):
    """Generate a scoped search key locally using HMAC.

    This replicates the Typesense client's generate_scoped_search_key
    logic so we don't need a full client instance.

    :param search_api_key: The search-only API key
    :param params: dict of parameters to embed
    :returns: base64-encoded scoped key string
    """
    params_str = json.dumps(params)
    digest = base64.b64encode(
        hmac.new(
            search_api_key.encode("utf-8"),
            params_str.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest(),
    )
    key_prefix = search_api_key[:4]
    raw_scoped_key = f"{digest.decode('utf-8')}{key_prefix}{params_str}"
    return base64.b64encode(raw_scoped_key.encode("utf-8")).decode("utf-8")


def generate_scoped_search_key(search_api_key, collection_name, user=None):
    """Generate a scoped search API key for a user.

    The scoped key embeds the user's allowedRolesAndUsers as a filter_by
    parameter, so the user can only see documents they have access to.

    :param search_api_key: The search-only API key to scope
    :param collection_name: The collection name to restrict to
    :param user: The user to scope for (defaults to current user)
    :returns: scoped API key string
    :raises ValueError: if search_api_key is empty
    """
    if not search_api_key:
        raise ValueError("A search-only API key is required to generate scoped keys")

    allowed = get_allowed_roles_and_users(user)
    filter_by = build_filter_by(allowed)

    params = {
        "filter_by": filter_by,
        "collection": collection_name,
    }

    log.debug(f"Generating scoped key with filter: {filter_by}")
    return _generate_scoped_key(search_api_key, params)
