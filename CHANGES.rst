Changelog
=========


1.0a2 (2026-03-16)
------------------

Bug fixes:

- Fix indexing pipeline to properly handle content indexing and reindexing.
  [MrTango]

- Fix permission checks in management views for proper access control.
  [MrTango]

- Fix error handling in Typesense connector for robustness during
  network failures and invalid responses.
  [MrTango]

- Fix queue processor to correctly batch and retry failed operations.
  [MrTango]

- Fix catalog patching to avoid conflicts with other catalog integrations.
  [MrTango]

New features:

- Add TypesenseFilterBuilder for constructing validated ``filter_by`` strings
  with support for exact match, numeric range, geo, and boolean filters.
  [MrTango]

- Add Typesense-native query methods with support for negation, phrase
  search, and field-weighted queries.
  [MrTango]

- Add custom search view to prevent Plone from mangling Typesense
  search terms.
  [MrTango]

- Add faceted search API with configurable highlighting settings in
  the control panel.
  [MrTango]

- Add synchronize view for bidirectional catalog/Typesense data sync.
  [MrTango]

- Add convert catalog view to initialize Typesense collections from
  the Plone catalog.
  [MrTango]

- Add data sync indicator to the control panel showing index health.
  [MrTango]

- Add MappingAdapter and IMappingProvider interface for auto-generating
  Typesense schemas from Plone catalog indexes.
  [MrTango]

- Add catalog-driven collection initialization to TypesenseConnector.
  [MrTango]

- Add schema diff detection and generation buttons to the control panel.
  [MrTango]

- Add REST API service endpoints for Typesense operations
  (``@typesense-search``, ``@typesense-status``, ``@typesense-reindex``).
  [MrTango]

- Add connection resilience with multi-node support, automatic retries,
  and environment variable API key fallback.
  [MrTango]

Internal:

- Migrate build system from buildout/tox to uv and pyproject.toml.
  [MrTango]

- Add GitHub Actions CI/CD workflow with test and lint jobs.
  [MrTango]

- Remove legacy Elasticsearch-style code: QueryAssembler, get_query() methods,
  getIndex aliases, dict path fallback, create_mapping(), extract() methods,
  and backward-compat aliases.
  [MrTango]


1.0a1 (unreleased)
------------------

- Initial release.
  [MrTango]
