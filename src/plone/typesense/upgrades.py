# -*- coding: utf-8 -*-
"""Upgrade steps for plone.typesense."""

from plone.typesense import log


def reload_profile(context):
    """Reload the full GenericSetup profile.

    This is useful when registry records or other profile-managed
    resources have changed.
    """
    context.runAllImportStepsFromProfile("profile-plone.typesense:default")
    log.info("plone.typesense profile reloaded.")


def upgrade_to_2(context):
    """Upgrade from version 1 to version 2.

    Re-imports the registry configuration to pick up any new or
    changed control panel settings.
    """
    context.runImportStepFromProfile(
        "profile-plone.typesense:default", "plone.app.registry"
    )
    log.info("plone.typesense upgraded to version 2.")
