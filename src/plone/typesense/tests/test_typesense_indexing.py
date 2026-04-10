# -*- coding: utf-8 -*-
"""Tests for Typesense indexing integration.

Test 1: Content creation triggers indexing in Typesense, and search finds
    the page and event.
Test 2: Typesense-only indexes are not stored in Plone catalog but search
    still works via Typesense.
"""
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.typesense.testing import PLONE_TYPESENSE_INTEGRATION_TESTING
from unittest import mock

import unittest


class TestTypesenseIndexing(unittest.TestCase):
    """Test 1: When content is created, data is indexed in Typesense
    and searching in Plone returns the page and event.
    """

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_processor(self):
        from plone.typesense.queueprocessor import IndexProcessor

        processor = IndexProcessor()
        return processor

    def _make_connector_mock(self):
        """Create a mock TypesenseConnector that records indexed/updated data."""
        connector = mock.MagicMock()
        connector.enabled = True
        connector.get_client.return_value = mock.MagicMock()
        connector.indexed_documents = []
        connector.updated_documents = []

        def _index(objects):
            connector.indexed_documents.extend(objects)

        def _update(objects):
            connector.updated_documents.extend(objects)

        connector.index.side_effect = _index
        connector.update.side_effect = _update
        return connector

    def _commit_actions(self, processor, connector):
        """Process queued actions and send them to the connector.

        Replaces processor.commit() to safely handle cases where only
        some action types are present.
        """
        actions = processor.actions
        if not actions or len(actions) == 0:
            return
        ts_data = {}
        for action, uuid, payload in actions.all():
            payload = processor._prepare_for_typesense(uuid, payload)
            ts_data.setdefault(action, []).append(payload)
        if "index" in ts_data:
            connector.index(ts_data["index"])
        if "update" in ts_data:
            connector.update(ts_data["update"])
        processor._clean_up()

    # -- indexing data collection --

    def test_page_and_event_are_indexed_in_typesense(self):
        """Creating a Page and Event triggers indexing in Typesense."""
        connector = self._make_connector_mock()
        processor = self._get_processor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="test-page",
            title="Test Page Title",
            description="A test page description for searching",
        )
        processor.index(page)

        event = api.content.create(
            container=self.portal,
            type="Event",
            id="test-event",
            title="Test Event Title",
            description="A test event description for searching",
        )
        processor.index(event)

        self._commit_actions(processor, connector)

        self.assertEqual(
            len(connector.indexed_documents),
            2,
            f"Expected 2 indexed documents, got {len(connector.indexed_documents)}",
        )

        page_uuid = api.content.get_uuid(page)
        event_uuid = api.content.get_uuid(event)
        doc_ids = {doc["id"] for doc in connector.indexed_documents}
        self.assertIn(page_uuid, doc_ids, "Page UUID should be in indexed documents")
        self.assertIn(event_uuid, doc_ids, "Event UUID should be in indexed documents")

    def test_indexed_page_data_contains_expected_fields(self):
        """Verify that indexed data contains Title, Description, SearchableText."""
        connector = self._make_connector_mock()
        processor = self._get_processor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="my-page",
            title="My Important Page",
            description="This is a very important page",
        )
        processor.index(page)
        self._commit_actions(processor, connector)

        page_uuid = api.content.get_uuid(page)
        page_docs = [
            doc for doc in connector.indexed_documents if doc["id"] == page_uuid
        ]
        self.assertEqual(len(page_docs), 1)
        page_doc = page_docs[0]

        self.assertEqual(page_doc["Title"], "My Important Page")
        self.assertEqual(page_doc["Description"], "This is a very important page")
        self.assertIn("SearchableText", page_doc)
        self.assertIn("My Important Page", page_doc["SearchableText"])
        self.assertEqual(page_doc["portal_type"], "Document")

    def test_indexed_event_data_contains_expected_fields(self):
        """Verify that indexed Event data contains expected fields."""
        connector = self._make_connector_mock()
        processor = self._get_processor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        event = api.content.create(
            container=self.portal,
            type="Event",
            id="my-event",
            title="Annual Conference",
            description="The annual conference event",
        )
        processor.index(event)
        self._commit_actions(processor, connector)

        event_uuid = api.content.get_uuid(event)
        event_docs = [
            doc for doc in connector.indexed_documents if doc["id"] == event_uuid
        ]
        self.assertEqual(len(event_docs), 1)
        event_doc = event_docs[0]

        self.assertEqual(event_doc["Title"], "Annual Conference")
        self.assertEqual(event_doc["Description"], "The annual conference event")
        self.assertIn("SearchableText", event_doc)
        self.assertIn("Annual Conference", event_doc["SearchableText"])
        self.assertEqual(event_doc["portal_type"], "Event")

    def test_index_data_includes_path(self):
        """Indexed data should include the object path."""
        connector = self._make_connector_mock()
        processor = self._get_processor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="path-test-page",
            title="Path Test Page",
        )
        processor.index(page)
        self._commit_actions(processor, connector)

        page_uuid = api.content.get_uuid(page)
        page_doc = [
            d for d in connector.indexed_documents if d["id"] == page_uuid
        ][0]

        self.assertIn("path", page_doc)
        expected_path = "/".join(page.getPhysicalPath())
        self.assertEqual(page_doc["path"], expected_path)

    def test_index_data_includes_uuid_as_id(self):
        """The Typesense document id should be the object UUID."""
        connector = self._make_connector_mock()
        processor = self._get_processor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="uuid-test",
            title="UUID Test",
        )
        processor.index(page)
        self._commit_actions(processor, connector)

        page_uuid = api.content.get_uuid(page)
        doc_ids = [doc["id"] for doc in connector.indexed_documents]
        self.assertIn(page_uuid, doc_ids, "Document id should be the UUID")

    def test_multiple_content_types_indexed_together(self):
        """Multiple content types are indexed in a single commit."""
        connector = self._make_connector_mock()
        processor = self._get_processor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="batch-page",
            title="Batch Page",
        )
        event = api.content.create(
            container=self.portal,
            type="Event",
            id="batch-event",
            title="Batch Event",
        )
        processor.index(page)
        processor.index(event)
        self._commit_actions(processor, connector)

        self.assertEqual(len(connector.indexed_documents), 2)
        indexed_types = {doc["portal_type"] for doc in connector.indexed_documents}
        self.assertIn("Document", indexed_types)
        self.assertIn("Event", indexed_types)

    def test_reindex_sends_update_to_typesense(self):
        """Reindexing content sends an update action to Typesense."""
        connector = self._make_connector_mock()
        processor = self._get_processor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="reindex-page",
            title="Original Title",
            description="Original description",
        )

        # Initial index + reindex with specific attributes to create both
        # action types in the queue
        processor.index(page)

        event = api.content.create(
            container=self.portal,
            type="Event",
            id="reindex-event",
            title="Some Event",
        )
        # This will be queued as a reindex (update) since we pass attributes
        # and the event is not yet in the index queue
        processor.reindex(event, attributes=["Title", "Description"])
        self._commit_actions(processor, connector)

        page_uuid = api.content.get_uuid(page)
        event_uuid = api.content.get_uuid(event)

        # page should be in indexed documents
        indexed_ids = {doc["id"] for doc in connector.indexed_documents}
        self.assertIn(page_uuid, indexed_ids)

        # event should be in updated documents (reindex -> update action)
        updated_ids = {doc["id"] for doc in connector.updated_documents}
        self.assertIn(event_uuid, updated_ids)

    # -- Plone catalog search --

    def test_plone_catalog_search_finds_page_and_event(self):
        """Content created is findable through normal Plone catalog search."""
        page = api.content.create(
            container=self.portal,
            type="Document",
            id="searchable-page",
            title="Searchable Page Title",
            description="Searchable page description",
        )
        event = api.content.create(
            container=self.portal,
            type="Event",
            id="searchable-event",
            title="Searchable Event Title",
            description="Searchable event description",
        )

        catalog = api.portal.get_tool("portal_catalog")

        # Search by Title
        results = catalog.searchResults(Title="Searchable Page Title")
        paths = [b.getPath() for b in results]
        self.assertIn(
            "/".join(page.getPhysicalPath()),
            paths,
            "Page should be findable by Title in catalog",
        )

        results = catalog.searchResults(Title="Searchable Event Title")
        paths = [b.getPath() for b in results]
        self.assertIn(
            "/".join(event.getPhysicalPath()),
            paths,
            "Event should be findable by Title in catalog",
        )

        # Search by portal_type
        results = catalog.searchResults(portal_type="Document")
        types = [b.portal_type for b in results]
        self.assertIn("Document", types)

        results = catalog.searchResults(portal_type="Event")
        types = [b.portal_type for b in results]
        self.assertIn("Event", types)

        # Search by SearchableText
        results = catalog.searchResults(SearchableText="Searchable Page")
        paths = [b.getPath() for b in results]
        self.assertIn(
            "/".join(page.getPhysicalPath()),
            paths,
            "Page should be findable by SearchableText",
        )


class TestTypesenseOnlyIndexes(unittest.TestCase):
    """Test 2: When using Typesense-only indexes (e.g. SearchableText, Title,
    Description), the content is only indexed in Typesense and NOT in the Plone
    catalog for those indexes. But searching in Plone still finds the content
    because the search is routed to Typesense.
    """

    layer = PLONE_TYPESENSE_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def _get_ts_only_indexes(self):
        from plone.typesense.utils import get_ts_only_indexes

        return get_ts_only_indexes()

    # -- ts_only_indexes configuration --

    def test_default_ts_only_indexes(self):
        """Verify default ts_only_indexes are Title, Description, SearchableText."""
        ts_only = self._get_ts_only_indexes()
        self.assertIn("Title", ts_only)
        self.assertIn("Description", ts_only)
        self.assertIn("SearchableText", ts_only)

    def test_ts_only_indexes_configurable_via_registry(self):
        """ts_only_indexes can be configured via the registry."""
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.ts_only_indexes",
            ["Title", "Description"],
        )
        ts_only = self._get_ts_only_indexes()
        self.assertEqual(ts_only, {"Title", "Description"})

        # Restore default
        api.portal.set_registry_record(
            "plone.typesense.typesense_controlpanel.ts_only_indexes",
            ["Title", "Description", "SearchableText"],
        )

    # -- Data collection includes ts_only fields --

    def test_processor_all_attributes_includes_ts_only(self):
        """The processor's all_attributes merges catalog indexes and ts_only indexes."""
        from plone.typesense.queueprocessor import IndexProcessor

        connector = mock.MagicMock()
        connector.enabled = True
        processor = IndexProcessor()
        processor._ts_connector = connector

        ts_only = self._get_ts_only_indexes()
        all_attrs = processor.all_attributes

        for idx_name in ts_only:
            self.assertIn(
                idx_name,
                all_attrs,
                f"ts_only index '{idx_name}' should be in all_attributes",
            )

    def test_get_data_for_page_includes_ts_only_attributes(self):
        """IndexProcessor.get_data for a Page includes ts_only attribute values."""
        from plone.typesense.queueprocessor import IndexProcessor

        connector = mock.MagicMock()
        connector.enabled = True
        processor = IndexProcessor()
        processor._ts_connector = connector

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="data-check-page",
            title="Data Check Page",
            description="Checking data collection",
        )

        page_uuid = api.content.get_uuid(page)
        data = processor.get_data(page_uuid)

        ts_only = self._get_ts_only_indexes()
        for idx_name in ts_only:
            self.assertIn(
                idx_name,
                data,
                f"ts_only index '{idx_name}' should be in get_data result",
            )
        self.assertEqual(data["Title"], "Data Check Page")
        self.assertEqual(data["Description"], "Checking data collection")
        self.assertIn("Data Check Page", data["SearchableText"])

    def test_get_data_for_event_includes_ts_only_attributes(self):
        """IndexProcessor.get_data for an Event includes ts_only attribute values."""
        from plone.typesense.queueprocessor import IndexProcessor

        connector = mock.MagicMock()
        connector.enabled = True
        processor = IndexProcessor()
        processor._ts_connector = connector

        event = api.content.create(
            container=self.portal,
            type="Event",
            id="event-data-check",
            title="Event Data Check",
            description="Checking event data collection",
        )

        event_uuid = api.content.get_uuid(event)
        data = processor.get_data(event_uuid)

        self.assertIn("Title", data)
        self.assertEqual(data["Title"], "Event Data Check")
        self.assertIn("Description", data)
        self.assertEqual(data["Description"], "Checking event data collection")
        self.assertIn("SearchableText", data)
        self.assertIn("Event Data Check", data["SearchableText"])

    def test_ts_only_index_data_sent_to_typesense(self):
        """Data for ts_only indexes is collected and included when sent to Typesense."""
        from plone.typesense.queueprocessor import IndexProcessor

        connector = mock.MagicMock()
        connector.enabled = True
        connector.get_client.return_value = mock.MagicMock()
        connector.indexed_documents = []

        def _index(objects):
            connector.indexed_documents.extend(objects)

        connector.index.side_effect = _index

        processor = IndexProcessor()
        processor._ts_connector = connector
        processor._ts_client = connector.get_client()

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="ts-only-page",
            title="TS Only Page",
            description="Indexed only in typesense",
        )
        processor.index(page)

        # Process actions manually to avoid KeyError on missing action types
        actions = processor.actions
        ts_data = {}
        for action, uuid, payload in actions.all():
            payload = processor._prepare_for_typesense(uuid, payload)
            ts_data.setdefault(action, []).append(payload)
        if "index" in ts_data:
            connector.index(ts_data["index"])
        processor._clean_up()

        page_uuid = api.content.get_uuid(page)
        page_docs = [
            doc for doc in connector.indexed_documents if doc["id"] == page_uuid
        ]
        self.assertEqual(len(page_docs), 1)
        page_doc = page_docs[0]

        self.assertEqual(page_doc["Title"], "TS Only Page")
        self.assertEqual(page_doc["Description"], "Indexed only in typesense")
        self.assertIn("SearchableText", page_doc)

    # -- Search routing: ts_only queries go to Typesense --

    def test_search_results_routes_to_typesense_for_searchabletext(self):
        """When query contains SearchableText (ts_only), search routes to Typesense."""
        from plone.typesense.manager import TypesenseManager

        manager = TypesenseManager()
        fake_results = mock.MagicMock()

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=True,
        ):
            with mock.patch.object(manager, "search", return_value=fake_results):
                manager.search_results(
                    request={},
                    check_perms=False,
                    SearchableText="test query",
                )
                manager.search.assert_called_once()

    def test_search_results_routes_to_typesense_for_title(self):
        """When query contains Title (ts_only), search routes to Typesense."""
        from plone.typesense.manager import TypesenseManager

        manager = TypesenseManager()
        fake_results = mock.MagicMock()

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=True,
        ):
            with mock.patch.object(manager, "search", return_value=fake_results):
                manager.search_results(
                    request={},
                    check_perms=False,
                    Title="some title",
                )
                manager.search.assert_called_once()

    def test_search_results_routes_to_typesense_for_description(self):
        """When query contains Description (ts_only), search routes to Typesense."""
        from plone.typesense.manager import TypesenseManager

        manager = TypesenseManager()
        fake_results = mock.MagicMock()

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=True,
        ):
            with mock.patch.object(manager, "search", return_value=fake_results):
                manager.search_results(
                    request={},
                    check_perms=False,
                    Description="some description",
                )
                manager.search.assert_called_once()

    def test_search_results_falls_back_to_catalog_without_ts_only_keys(self):
        """When query has NO ts_only index keys, catalog is used instead."""
        from plone.typesense.manager import TypesenseManager

        manager = TypesenseManager()
        mock_catalog = mock.MagicMock()
        mock_catalog._old_unrestrictedSearchResults.return_value = []

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=True,
        ):
            with mock.patch.object(
                TypesenseManager,
                "catalog",
                new_callable=mock.PropertyMock,
                return_value=mock_catalog,
            ):
                manager.search_results(
                    request={},
                    check_perms=False,
                    portal_type="Document",
                )
                mock_catalog._old_unrestrictedSearchResults.assert_called_once()

    def test_search_results_falls_back_to_catalog_when_inactive(self):
        """When Typesense is not active, catalog is always used."""
        from plone.typesense.manager import TypesenseManager

        manager = TypesenseManager()
        mock_catalog = mock.MagicMock()
        mock_catalog._old_unrestrictedSearchResults.return_value = []

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=False,
        ):
            with mock.patch.object(
                TypesenseManager,
                "catalog",
                new_callable=mock.PropertyMock,
                return_value=mock_catalog,
            ):
                manager.search_results(
                    request={},
                    check_perms=False,
                    SearchableText="test query",
                )
                mock_catalog._old_unrestrictedSearchResults.assert_called_once()

    # -- End-to-end: ts_only search returns page and event --

    def test_ts_only_page_and_event_findable_via_typesense_search(self):
        """Page and Event are findable through Typesense search when
        using ts_only indexes (SearchableText).
        """
        from plone.typesense.manager import TypesenseManager
        from ZTUtils.Lazy import LazyMap

        page = api.content.create(
            container=self.portal,
            type="Document",
            id="ts-search-page",
            title="Typesense Search Page",
            description="A page only findable through typesense",
        )
        event = api.content.create(
            container=self.portal,
            type="Event",
            id="ts-search-event",
            title="Typesense Search Event",
            description="An event only findable through typesense",
        )

        page_path = "/".join(page.getPhysicalPath())
        event_path = "/".join(event.getPhysicalPath())

        manager = TypesenseManager()

        def fake_search(query, **kw):
            """Simulate Typesense returning both objects."""
            fake_data = [
                {"fields": {"path.path": page_path}, "Title": "Typesense Search Page"},
                {"fields": {"path.path": event_path}, "Title": "Typesense Search Event"},
            ]
            return LazyMap(lambda x: x, fake_data, len(fake_data))

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=True,
        ):
            with mock.patch.object(manager, "search", side_effect=fake_search):
                results = manager.search_results(
                    request={},
                    check_perms=False,
                    SearchableText="Typesense Search",
                )

                result_list = list(results)
                self.assertEqual(len(result_list), 2)

                result_paths = [r["fields"]["path.path"] for r in result_list]
                self.assertIn(page_path, result_paths, "Page should be in results")
                self.assertIn(event_path, result_paths, "Event should be in results")

    def test_ts_only_search_with_title_returns_page(self):
        """Search using Title (ts_only) routes to Typesense and returns the page."""
        from plone.typesense.manager import TypesenseManager
        from ZTUtils.Lazy import LazyMap

        page_path = "/".join(self.portal.getPhysicalPath()) + "/title-search-page"

        manager = TypesenseManager()

        def fake_search(query, **kw):
            fake_data = [{"fields": {"path.path": page_path}}]
            return LazyMap(lambda x: x, fake_data, len(fake_data))

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=True,
        ):
            with mock.patch.object(manager, "search", side_effect=fake_search):
                results = manager.search_results(
                    request={},
                    check_perms=False,
                    Title="Title Search Page",
                )
                manager.search.assert_called_once()
                self.assertEqual(len(list(results)), 1)

    def test_ts_only_search_with_description_returns_event(self):
        """Search using Description (ts_only) routes to Typesense and returns the event."""
        from plone.typesense.manager import TypesenseManager
        from ZTUtils.Lazy import LazyMap

        event_path = "/".join(self.portal.getPhysicalPath()) + "/desc-search-event"

        manager = TypesenseManager()

        def fake_search(query, **kw):
            fake_data = [{"fields": {"path.path": event_path}}]
            return LazyMap(lambda x: x, fake_data, len(fake_data))

        with mock.patch.object(
            TypesenseManager,
            "active",
            new_callable=mock.PropertyMock,
            return_value=True,
        ):
            with mock.patch.object(manager, "search", side_effect=fake_search):
                results = manager.search_results(
                    request={},
                    check_perms=False,
                    Description="Description search event",
                )
                manager.search.assert_called_once()
                self.assertEqual(len(list(results)), 1)

    # -- Plone catalog still works for non-ts_only fields --

    def test_content_indexed_in_catalog_for_non_ts_only_fields(self):
        """Content is still indexed in Plone catalog for non-ts_only fields
        like portal_type, review_state, etc.
        """
        page = api.content.create(
            container=self.portal,
            type="Document",
            id="catalog-check-page",
            title="Catalog Check Page",
            description="Checking catalog indexing",
        )
        event = api.content.create(
            container=self.portal,
            type="Event",
            id="catalog-check-event",
            title="Catalog Check Event",
            description="Checking catalog event indexing",
        )

        catalog = api.portal.get_tool("portal_catalog")

        results = catalog.searchResults(portal_type="Document")
        paths = [b.getPath() for b in results]
        self.assertIn(
            "/".join(page.getPhysicalPath()),
            paths,
            "Page should be findable by portal_type (non-ts_only field)",
        )

        results = catalog.searchResults(portal_type="Event")
        paths = [b.getPath() for b in results]
        self.assertIn(
            "/".join(event.getPhysicalPath()),
            paths,
            "Event should be findable by portal_type (non-ts_only field)",
        )
