import json
import os
import threading

import typesense
from plone import api
from plone.typesense import _, log
from zope.interface import Interface, implementer


class TypesenseError(Exception):
    def __init__(self, reason, exit_status=1):
        self.reason = reason
        self.exit_status = exit_status

    def __str__(self):
        return "<TypesenseError %r %d>" % (self.reason, self.exit_status)


class ITypesenseConnector(Interface):
    """Marker for TypesenseConnector"""


@implementer(ITypesenseConnector)
class TypesenseConnector:
    """Typesense connection utility"""

    def __init__(self):
        self.data = threading.local()
        self.data.client = None

    @property
    def enabled(self):
        try:
            return api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.enabled"
            )
        except api.exc.InvalidParameterError:
            value = False
        return value

    @property
    def collection_base_name(self):
        return api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.collection"
        )

    @property
    def get_api_key(self):
        try:
            key = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.api_key"
            )
            if key:
                return key
        except api.exc.InvalidParameterError as e:
            log.warn(f"could not load Typesense API key from registry: {e}")
        # Fall back to environment variable
        env_key = os.environ.get("TYPESENSE_API_KEY")
        if env_key:
            log.info("Using Typesense API key from TYPESENSE_API_KEY environment variable")
            return env_key
        return None

    @property
    def get_timeout(self):
        return api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.timeout"
        )

    @property
    def get_host(self):
        try:
            host = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.host"
            )
            if host:
                return host
        except api.exc.InvalidParameterError as e:
            log.warn(f"could not load Typesense host from registry: {e}")
        env_host = os.environ.get("TYPESENSE_HOST")
        if env_host:
            log.info("Using Typesense host from TYPESENSE_HOST environment variable")
            return env_host
        return "localhost"

    @property
    def get_port(self):
        try:
            port = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.port"
            )
            if port:
                return port
        except api.exc.InvalidParameterError as e:
            log.warn(f"could not load Typesense port from registry: {e}")
        env_port = os.environ.get("TYPESENSE_PORT")
        if env_port:
            log.info("Using Typesense port from TYPESENSE_PORT environment variable")
            return env_port
        return "8108"

    @property
    def get_protocol(self):
        try:
            protocol = api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.protocol"
            )
            if protocol:
                return protocol
        except api.exc.InvalidParameterError as e:
            log.warn(f"could not load Typesense protocol from registry: {e}")
        env_protocol = os.environ.get("TYPESENSE_PROTOCOL")
        if env_protocol:
            log.info("Using Typesense protocol from TYPESENSE_PROTOCOL environment variable")
            return env_protocol
        return "http"

    @property
    def get_ts_schema(self):
        return api.portal.get_registry_record(
            "plone.typesense.typesense_controlpanel.ts_schema"
        )

    @property
    def get_additional_nodes(self):
        try:
            return api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.additional_nodes"
            )
        except api.exc.InvalidParameterError:
            return ""

    @property
    def get_num_retries(self):
        try:
            return api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.num_retries"
            )
        except api.exc.InvalidParameterError:
            return 3

    @property
    def get_retry_interval_seconds(self):
        try:
            return api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.retry_interval_seconds"
            )
        except api.exc.InvalidParameterError:
            return 1.0

    @property
    def get_healthcheck_interval_seconds(self):
        try:
            return api.portal.get_registry_record(
                "plone.typesense.typesense_controlpanel.healthcheck_interval_seconds"
            )
        except api.exc.InvalidParameterError:
            return 60

    def _parse_additional_nodes(self):
        """Parse additional_nodes text into a list of node dicts.

        Each line should be in the format: host:port:protocol
        Lines that don't match this format are skipped with a warning.
        """
        raw = self.get_additional_nodes
        if not raw:
            return []
        nodes = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 3:
                log.warn(
                    f"Skipping invalid additional node definition: '{line}'. "
                    f"Expected format: host:port:protocol"
                )
                continue
            host, port_str, protocol = parts
            try:
                port = int(port_str)
            except ValueError:
                log.warn(
                    f"Skipping additional node with invalid port: '{line}'"
                )
                continue
            nodes.append({"host": host, "port": port, "protocol": protocol})
        return nodes

    def get_client(self):
        """ """
        client = getattr(self.data, "client", None)
        if client:
            return client
        api_key = self.get_api_key
        if not api_key:
            raise ValueError(_("No Typesense API key(s) configured"))
        connection_timeout = self.get_timeout
        ts_host = self.get_host
        ts_port = self.get_port
        ts_protocol = self.get_protocol

        # Build nodes list: primary node first, then additional nodes
        nodes = [
            {
                "host": ts_host,
                "port": int(ts_port),
                "protocol": ts_protocol,
            }
        ]
        nodes.extend(self._parse_additional_nodes())

        client_config = {
            "nodes": nodes,
            "api_key": api_key,
            "connection_timeout_seconds": int(connection_timeout) or 10,
            "num_retries": self.get_num_retries or 3,
            "retry_interval_seconds": self.get_retry_interval_seconds or 1.0,
            "healthcheck_interval_seconds": self.get_healthcheck_interval_seconds or 60,
        }
        self.data.client = typesense.Client(client_config)
        return self.data.client

    def test_connection(self):
        ts = self.get_client()
        try:
            ts.collections.retrieve()
        except typesense.exceptions.ObjectNotFound as exc:
            raise TypesenseError(
                _("Not Found - The requested resource is not found.")
            ) from exc
        except typesense.RequestUnauthorized as exc:
            raise TypesenseError(_("Unauthorized - Your API key is wrong.")) from exc
        except typesense.TypesenseClientError as exc:
            raise TypesenseError(_("Unable to connect :") + "\n\n" + repr(exc)) from exc

    def _get_current_aliased_collection_name(self) -> str:
        """Get the current aliased index name if any"""
        ts = self.get_client()
        current_aliased_index_name = None
        alias = ts.aliases[self.collection_base_name].retrieve()
        if "collection_name" in alias:
            current_aliased_index_name = alias["collection_name"]
        return current_aliased_index_name

    def _get_next_aliased_collection_name(
        self, aliased_index_name: str | None = None
    ) -> str:
        """Get the next aliased index name

        The next aliased collection name is based on the current aliased collection name.
        It's the current aliased collection name incremented by 1.

        :param aliased_index_name: the current aliased index name
        :return: the next aliased index name
        """
        next_version = 1
        if aliased_index_name:
            next_version = int(aliased_index_name.split("-")[-1]) + 1
        return f"{self.collection_base_name}-{next_version}"

    def update(self, objects) -> None:
        """update given objects"""
        if not objects:
            return
        ts = self.get_client()
        for obj in objects:
            log.info(f"Updating object: {obj.get('id', 'unknown')}")
            ts.collections[self.collection_base_name].documents[obj["id"]].update(obj)

    def index(self, objects) -> None:
        """index given objects"""
        if not objects:
            return
        ts = self.get_client()
        log.info(f"Indexing {len(objects)} objects into '{self.collection_base_name}'.")
        ts.collections[self.collection_base_name].documents.import_(
            objects, {"action": "upsert"}
        )

    def delete(self, uids) -> None:
        """Delete documents by their UIDs from Typesense."""
        if not uids:
            return
        ts = self.get_client()
        log.info(
            f"Delete {len(uids)} uids from collection "
            f"'{self.collection_base_name}'."
        )
        uid_list = ",".join([f"`{uid}`" for uid in uids])
        ts.collections[self.collection_base_name].documents.delete(
            {"filter_by": f"id:[{uid_list}]"}
        )

    def clear(self) -> None:
        """ """
        ts = self.get_client()
        collection_name = (
            self._get_current_aliased_collection_name() or self.collection_base_name
        )
        log.info(f"Clear current_aliased_collection_name '{collection_name}'.")
        ts.collections[collection_name].delete()
        self.init_collection()

    def sync_synonyms(self, synonym_rules: list) -> tuple:
        """Sync synonym rules to the current collection.

        :param synonym_rules: list of synonym dicts from parse_synonyms()
        :returns: tuple of (upserted_count, errors)
        """
        from plone.typesense.synonyms import sync_synonyms
        ts = self.get_client()
        return sync_synonyms(ts, self.collection_base_name, synonym_rules)

    def init_collection(self, schema=None) -> None:
        """Initialize a Typesense collection.

        :param schema: Optional schema dict. If not provided, uses the
            schema from the control panel registry (ts_schema).
            When a catalog is available, callers can use
            ``convert_catalog_to_typesense()`` from ``plone.typesense.mapping``
            to auto-generate a schema from catalog indexes.
        """
        ts = self.get_client()
        try:
            ts.collections[self.collection_base_name].retrieve()
        except typesense.exceptions.ObjectNotFound:
            # To allow rolling updates, we work with index aliases
            aliased_index_name = self._get_next_aliased_collection_name()
            index_config = schema if schema else self.get_ts_schema
            # Ensure we use a copy so we don't mutate the original
            index_config = dict(index_config)
            index_config["name"] = aliased_index_name
            log.info(f"Create aliased_index_name '{aliased_index_name}'...")
            ts.collections.create(index_config)
            log.info(
                f"Set collection alias '{self.collection_base_name}' >> aliased_index_name "
                f"'{aliased_index_name}'."
            )
            ts.aliases.upsert(
                self.collection_base_name, {"collection_name": aliased_index_name}
            )

    def init_collection_from_catalog(self, catalog) -> dict:
        """Initialize a Typesense collection using an auto-generated schema
        derived from the Plone catalog indexes.

        :param catalog: The Plone portal_catalog tool
        :returns: The generated schema dict
        """
        from plone.typesense.mapping import convert_catalog_to_typesense

        schema = convert_catalog_to_typesense(
            catalog, collection_name=self.collection_base_name
        )
        self.init_collection(schema=schema)
        return schema

    # def each(self) -> Iterator[dict[str, Any]]:
    #     """ """
    #     ts = self.get_client()
    #     res = ts.collections[self._index_name].documents.search(
    #         {
    #             "q": "*",
    #         }
    #     )
    #     if not res:
    #         # eg: empty index
    #         return
    #     hits = res["hits"]["documents"]
    #     for hit in hits:
    #         yield hit
