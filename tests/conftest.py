"""Pytest configuration for plone.typesense tests."""
import pytest

from plone.typesense.testing import FUNCTIONAL_TESTING
from plone.typesense.testing import INTEGRATION_TESTING


@pytest.fixture(scope="class")
def integration_testing():
    """Integration testing fixture."""
    return INTEGRATION_TESTING


@pytest.fixture(scope="class")
def functional_testing():
    """Functional testing fixture."""
    return FUNCTIONAL_TESTING
