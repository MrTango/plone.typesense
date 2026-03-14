# Gap Analysis & Roadmap: plone.typesense vs collective.elasticsearch — Improved Plan

## Context

plone.typesense is a Typesense integration for Plone modeled after collective.elasticsearch. While the architecture (query routing, index adapters, result handling) is sound, the codebase has **critical bugs that make it non-functional** and **missing features** compared to the mature c.elasticsearch package. This plan addresses bugs first, then gaps, in a phased roadmap to production readiness.

---

## CRITICAL BUGS (Must fix before any feature work)

These are **broken code**, not missing features. All verified against actual source:

| # | Bug | File:Line | Impact |
|---|-----|-----------|--------|
| B1 | **Permission filtering disabled** — `check_perms = False` hardcoded | `manager.py:183` | OWASP A01:2021 — every search is unrestricted |
| B2 | **Fallback also unrestricted** — always uses `_old_unrestrictedSearchResults` because check_perms forced False | `manager.py:209-213` | Doubles the permission bypass impact |
| B3 | **unindex() is a no-op** — only prints, never queues delete | `queueprocessor.py:384-388` | Deleted content remains in Typesense |
| B4 | **commit_ts() ignores deletes** — no "delete" branch, only "index" and "update" | `queueprocessor.py:416-420` | Even if unindex queued, deletes never execute |
| B5 | **delete() wrong filter syntax** — `{"filter_by=id": uids}` is invalid | `global_utilities/typesense.py:193-194` | Delete API calls always fail |
| B6 | **json.dumps() passed to Typesense client** — client expects dicts, not JSON strings | `global_utilities/typesense.py:158,166` | **Entire indexing pipeline is broken** |
| B7 | **Reindex view crashes** — `return self.index()` calls nonexistent method | `views/typesense_reindex_collection.py:40` | Always raises AttributeError |
| B8 | **Reindex view double-indexing** — `if len(self.objects) > 0` inside loop callback | `views/typesense_reindex_collection.py:36-37` | Partial re-indexing on every batch |
| B9 | **TypesenseResult slice crash** — `range(key.start, key.end)` should be `.stop` | `result.py:175` | Any slice access raises AttributeError |
| B10 | **Brain highlighting crash** — `brain["Description"] = ...` unsupported | `result.py:104` | Highlighting always crashes |
| B11 | **TypesenseError(BaseException)** — won't be caught by `except Exception` | `global_utilities/typesense.py:10` | Errors escape all standard handlers |
| B12 | **Logging uses `object` builtin** — `log.info(f"object: {object}")` | `global_utilities/typesense.py:157,165` | Logs useless `<class 'object'>` |
| B13 | **Bulk import commented out** — individual upserts in loop instead of `documents.import_()` | `global_utilities/typesense.py:167-184` | Performance: N API calls instead of 1 |

---

## GAP ANALYSIS

### Legend
- **[MISSING]** — Not implemented at all
- **[STUB]** — Code exists but is non-functional
- **[PARTIAL]** — Partially implemented, needs completion
- **[BROKEN]** — Implemented but has bugs (see Critical Bugs above)
- **[OK]** — Implemented and equivalent

### 1. Catalog Patching

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| searchResults patch | Yes | Yes | **[OK]** |
| __call__ patch | Yes | Yes | **[OK]** |
| unrestrictedSearchResults patch | Yes | Yes, but check_perms broken | **[BROKEN]** B1,B2 |
| manage_catalogRebuild patch | Yes — syncs ES during rebuild | No | **[MISSING]** |
| manage_catalogClear patch | Yes — clears both catalog + ES | No | **[MISSING]** |
| uncatalog_object patch | Yes — removes from ES on delete | No | **[MISSING]** |
| moveObjectsByDelta patch | Yes — reindexes on reorder | No | **[MISSING]** |

### 2. Event Subscribers / Content Lifecycle

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Object created → index | Yes via IIndexQueueProcessor | Yes via IndexProcessor | **[OK]** |
| Object modified → reindex | Yes | Subscriber only prints | **[STUB]** |
| Object deleted → unindex | Yes via uncatalog_object patch | unindex() is no-op | **[BROKEN]** B3,B4 |
| Object moved/renamed → reindex | Yes | No | **[MISSING]** |
| Object copied → index | Yes | No | **[MISSING]** |
| Workflow transition → reindex | Yes via standard Plone events | No | **[MISSING]** |
| Transaction-aware queue | Yes begin/commit/abort | Yes begin/commit/abort | **[OK]** |

### 3. Index Management & Schema

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| MappingAdapter (schema from catalog) | Yes — auto-generates mapping | No — manual JSON schema | **[MISSING]** |
| IAdditionalIndexDataProvider | Yes — adapter lookup | Commented-out code | **[MISSING]** |
| IMappingProvider interface | Yes — external schema contributions | No | **[MISSING]** |
| Versioned index naming | Yes `{name}_{version}` | Yes `{name}-{version}` aliases | **[OK]** |
| Index alias management | Yes | Yes | **[OK]** |
| convert_catalog_to_engine() | Yes — initializes from catalog | No | **[MISSING]** |

### 4. Indexing Pipeline

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Single document upsert | Yes | json.dumps bug breaks it | **[BROKEN]** B6 |
| Bulk import | Yes | Commented out | **[BROKEN]** B13 |
| Delete documents | Yes | Wrong filter syntax | **[BROKEN]** B5 |
| IReindexActive marker | Yes — prevents recursion | Referenced in comment only | **[MISSING]** |

### 5. Browser Views & Maintenance

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Control panel form | Yes | Yes | **[OK]** |
| Connection status display | Yes — cluster health, doc counts | test_connection only | **[PARTIAL]** |
| Convert catalog view | Yes `@@elastic-convert` | No | **[MISSING]** |
| Rebuild/reindex view | Yes `@@elastic-rebuild` | Crashes on call | **[BROKEN]** B7,B8 |
| Synchronize view | Yes — bidirectional UID comparison | No | **[MISSING]** |
| Data sync indicator | Yes — doc count comparison | No | **[MISSING]** |
| CSRF protection on views | Yes | No | **[MISSING]** |

### 6. Search Features

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Full-text search | Yes | Yes | **[OK]** |
| Filter queries | Yes | Yes | **[OK]** |
| Sort support | Yes | Yes | **[OK]** |
| Highlighting | Yes — custom pre/post tags | Crashes on assignment | **[BROKEN]** B10 |
| Result slicing | Yes | Uses `.end` not `.stop` | **[BROKEN]** B9 |
| Negation queries (`not`) | Yes | No | **[MISSING]** |
| Phrase matching / boost | Yes — ZCTextIndex phrase matching | No | **[MISSING]** |
| Custom search view | Yes — overrides munge_search_term | No | **[MISSING]** |
| Faceted search / aggregations | Yes via ES aggregations | Fields marked facet:true but no aggregation API | **[PARTIAL]** |

### 7. REST API

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Info endpoint | Yes — returns cluster info | No | **[MISSING]** |
| Convert action (REST) | Yes — POST convert | No | **[MISSING]** |
| Rebuild action (REST) | Yes — POST rebuild | No | **[MISSING]** |
| Control panel REST adapter | Yes | Yes | **[OK]** |

### 8. Error Handling & Resilience

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Fallback to catalog on error | Yes | Yes (but unrestricted) | **[BROKEN]** B2 |
| Configurable raise_exception | Yes | Yes | **[OK]** |
| IReindexActive marker | Yes — prevents recursion | No | **[MISSING]** |
| Per-field error handling | Yes | Yes | **[OK]** |
| Connection retry / sniffing | Yes — sniff_on_start, retry_on_timeout | No | **[MISSING]** |
| TypesenseError exception class | N/A | Inherits BaseException, not Exception | **[BROKEN]** B11 |

### 9. Upgrades & Installation

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| GenericSetup upgrade steps | Yes — upgrades.py | No | **[MISSING]** |
| Profile versioning | Version 4 with history | Version 1000, no upgrades | **[MISSING]** |
| Post-install handler | Yes — functional | Empty stub | **[STUB]** |
| Uninstall handler | Yes — cleanup | Empty stub | **[STUB]** |

### 10. Code Quality

| Area | Issue | Severity |
|------|-------|----------|
| print() statements | ~215 occurrences across 9+ files, `from pprint import pprint` | HIGH |
| MockIndex duplication | Defined inline in both `queueprocessor.py:113` and `query.py:67` with subtle differences | MEDIUM |
| HTMLStripper duplication | Identical inner class at `indexes.py:327` and `indexes.py:383` | MEDIUM |
| Filter building | String concatenation, no validation | MEDIUM |
| API key storage | Plain TextLine in registry, no env-var fallback | MEDIUM |
| Dead commented-out code | Substantial in 5+ files | LOW |
| Thread-local inconsistency | Connector uses `threading.local()`, IndexProcessor caches `_ts_client` as instance attr | LOW |

### 11. Testing

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Search tests | 15KB+ comprehensive | ~568 lines | **[PARTIAL]** |
| Processor/indexing tests | 7.8KB | None | **[MISSING]** |
| Control panel tests | Yes | None | **[MISSING]** |
| REST API tests | Yes | None | **[MISSING]** |
| Permission filtering tests | Yes | None | **[MISSING]** |
| Delete/unindex tests | Yes | None | **[MISSING]** |
| Rename/move tests | Yes | None | **[MISSING]** |
| Test cleanup (teardown) | Index+alias cleanup | Basic | **[PARTIAL]** |

---

## ROADMAP

### Phase 0: Critical Bug Fixes — "Make it actually work"
**Effort:** 3-4 days | **Depends on:** Nothing

| # | Task | Bug Ref | Files |
|---|------|---------|-------|
| 0.1 | Fix `check_perms` — remove hardcoded `False`, respect caller param | B1 | `manager.py:183` |
| 0.2 | Fix fallback to use restricted search when `check_perms=True` | B2 | `manager.py:209-213` |
| 0.3 | Implement `unindex()` — add to `actions` dict, queue delete action | B3 | `queueprocessor.py:384-388` |
| 0.4 | Add "delete" branch to `commit_ts()` calling `ts_delete()` | B4 | `queueprocessor.py:416-420` |
| 0.5 | Fix `delete()` filter syntax to valid Typesense format | B5 | `global_utilities/typesense.py:193-194` |
| 0.6 | Fix `json.dumps()` — pass dicts to Typesense client, not strings | B6 | `global_utilities/typesense.py:158,166` |
| 0.7 | Fix reindex view: remove `self.index()`, fix double-indexing logic | B7,B8 | `views/typesense_reindex_collection.py` |
| 0.8 | Fix `TypesenseResult.__getitem__` slice: `.end` → `.stop` | B9 | `result.py:175` |
| 0.9 | Fix brain highlighting: use `setattr` or proper attribute assignment | B10 | `result.py:104` |
| 0.10 | Fix `TypesenseError` to inherit `Exception` not `BaseException` | B11 | `global_utilities/typesense.py:10` |
| 0.11 | Fix `log.info(f"object: {object}")` to use `obj` variable | B12 | `global_utilities/typesense.py:157,165` |
| 0.12 | Enable bulk import via `documents.import_()`, keep upsert as fallback | B13 | `global_utilities/typesense.py:160-184` |
| 0.13 | Extract `HTMLStripper` to module-level, remove duplicate | — | `indexes.py:327,383` |
| 0.14 | Replace all `print()`/`pprint()` with `log.debug()`/`log.info()` | — | 9+ files |
| 0.15 | Consolidate `MockIndex` to single location | — | `indexes.py`, `queueprocessor.py`, `query.py` |
| 0.16 | Add tests for all critical fixes | — | `tests/test_indexing_pipeline.py` (new) |

**Milestone: FUNCTIONAL** — CRUD operations work end-to-end, permissions enforced, no crashes.

---

### Phase 1: Catalog Lifecycle — "Keep Typesense in sync"
**Effort:** 5-7 days | **Depends on:** Phase 0

| # | Task | Files |
|---|------|-------|
| 1.1 | Implement event subscriber — trigger IndexProcessor on content events (create/modify/delete/move/copy/workflow) | `subscribers/index_in_typesense.py`, `subscribers/configure.zcml` |
| 1.2 | Add `IReindexActive` marker interface — prevent recursion during bulk ops | `interfaces.py` |
| 1.3 | Patch `uncatalog_object` — queue TS delete on object removal | `patches/__init__.py`, `patches/configure.zcml` |
| 1.4 | Patch `manage_catalogRebuild` — clear TS, flag IReindexActive, rebuild | `patches/__init__.py`, `patches/configure.zcml` |
| 1.5 | Patch `manage_catalogClear` — clear TS collection before original | `patches/__init__.py`, `patches/configure.zcml` |
| 1.6 | Add `IAdditionalIndexDataProvider` interface and wire adapter lookup | `interfaces.py`, `queueprocessor.py` |
| 1.7 | Rewrite reindex view with IndexProcessor + CSRF protection + progress tracking | `views/typesense_reindex_collection.py` |
| 1.8 | Add tests for patches, subscriber, reindex | `tests/test_patches.py`, `tests/test_controlpanel.py` (new) |

**Milestone: LIFECYCLE COMPLETE** — All catalog operations sync to Typesense.

---

### Phase 2: Search Feature Parity & Maintenance Views — "Match c.elasticsearch capabilities"
**Effort:** 7-10 days | **Depends on:** Phase 1

| # | Task | Files |
|---|------|-------|
| 2.1 | Implement synchronize view — bidirectional UID comparison, index missing, delete orphans | `views/typesense_sync.py` (new), `views/configure.zcml` |
| 2.2 | Implement convert catalog view — initialize Typesense from existing catalog | `views/typesense_convert.py` (new), `views/configure.zcml` |
| 2.3 | Add negation query support (`!=` filter syntax in Typesense) | `indexes.py`, `query.py` |
| 2.4 | Add phrase matching / boost for ZCTextIndex | `indexes.py` |
| 2.5 | Add custom search view — prevent Plone from mangling search terms | `browser/search.py` (new), `browser/configure.zcml` |
| 2.6 | Implement faceted search / aggregations API — expose Typesense facet counts | `manager.py`, `result.py` |
| 2.7 | Add data sync indicator to control panel — show doc count comparison | `controlpanels/typesense_controlpanel/controlpanel.py` |
| 2.8 | Improve highlighting — configurable pre/post tags in control panel | `controlpanels/`, `manager.py` |
| 2.9 | Add permission filtering + search feature tests | `tests/test_permissions.py`, `tests/test_search_advanced.py` (new) |

**Milestone: FEATURE PARITY** — All c.elasticsearch search and maintenance capabilities matched.

---

### Phase 3: Schema Management & REST API — "Production-grade admin tooling"
**Effort:** 10-14 days | **Depends on:** Phase 2

| # | Task | Files |
|---|------|-------|
| 3.1 | Implement MappingAdapter — auto-generate Typesense schema from catalog indexes | `mapping.py` (new) |
| 3.2 | Add `IMappingProvider` interface — external schema contributions | `interfaces.py`, `configure.zcml` |
| 3.3 | Add `convert_catalog_to_typesense()` — initialize collection from catalog state | `manager.py` or `mapping.py` |
| 3.4 | Schema diff detection — warn when catalog indexes change | `controlpanels/` |
| 3.5 | Add Typesense info REST endpoint — connection status, doc count, collection info | `services/typesense.py` (new), `services/configure.zcml` (new) |
| 3.6 | Add convert/rebuild/synchronize REST actions | `services/typesense.py` |
| 3.7 | TypesenseFilterBuilder class — replace string concatenation with validated builder | `filters.py` (new), update `indexes.py` |
| 3.8 | Add connection resilience — multi-node, retries, env-var API key fallback | `global_utilities/typesense.py`, `controlpanels/` |
| 3.9 | Tests for schema, REST API, filter builder | `tests/test_mapping.py`, `tests/test_services.py`, `tests/test_filter_builder.py` (new) |

**Milestone: PRODUCTION-READY** — Dynamic schema, REST management, resilient connections.

---

### Phase 4: Upgrades, Installation & Release — "Ship it"
**Effort:** 3-5 days | **Depends on:** Phase 3

| # | Task | Files |
|---|------|-------|
| 4.1 | Implement post_install handler — initialize collection on first install | `setuphandlers.py` |
| 4.2 | Implement uninstall handler — clean up Typesense collection | `setuphandlers.py` |
| 4.3 | Add GenericSetup upgrade steps — registry migration between versions | `upgrades.py` (new), `configure.zcml` |
| 4.4 | Set proper profile versioning — start from version 1 | `profiles/default/metadata.xml` |
| 4.5 | Add CHANGES.rst | `CHANGES.rst` (new) |
| 4.6 | Add CI/CD pipeline — GitHub Actions for tests on push | `.github/workflows/` (new) |
| 4.7 | PyPI packaging verification — ensure sdist/wheel builds cleanly | `pyproject.toml` |

**Milestone: RELEASED** — v1.0 on PyPI.

---

### Phase 5: Advanced Features (Post-release, optional)
**Effort:** Varies | **Depends on:** Phase 4

| # | Task | Priority | Files |
|---|------|----------|-------|
| 5.1 | Async queue support — optional Redis/RQ for background indexing | LOW | `async/` (new package) |
| 5.2 | Blob text extraction — extract text from PDF/DOCX | MEDIUM | `queueprocessor.py` |
| 5.3 | Patch `moveObjectsByDelta` — reindex positions on reorder | LOW | `patches/__init__.py` |
| 5.4 | Scoped API tokens — per-user search tokens with embedded filters | LOW | `manager.py`, `controlpanels/` |
| 5.5 | Synonym support — configurable synonym lists | LOW | `controlpanels/` |
| 5.6 | Semantic/vector search — leverage Typesense's vector search | LOW | New module |

---

## EXECUTION SCHEDULE

**Sprint 1 (Weeks 1-2):** Phase 0 (all)
- *Outcome: Working indexing pipeline, permissions enforced, no crashes, green tests*

**Sprint 2 (Weeks 3-4):** Phase 1 (all)
- *Outcome: Full catalog lifecycle sync, event-driven indexing*

**Sprint 3 (Weeks 5-7):** Phase 2 (all)
- *Outcome: Search feature parity, maintenance views, comprehensive tests*

**Sprint 4 (Weeks 8-10):** Phase 3 (all)
- *Outcome: Dynamic schema, REST API, production-grade resilience*

**Sprint 5 (Weeks 11-12):** Phase 4 (all)
- *Outcome: v1.0 released on PyPI*

**Post-release:** Phase 5 items as prioritized by users

---

## CRITICAL PATH (minimum viable v1.0)

1. **Fix indexing pipeline** (0.3-0.6) — without this, nothing indexes or deletes
2. **Fix permission filtering** (0.1-0.2) — without this, security is broken
3. **Fix crashes** (0.7-0.12) — without this, users hit errors immediately
4. **Implement event subscriber** (1.1) — without this, nothing auto-indexes
5. **Add uncatalog_object patch** (1.3) — without this, deletes leave orphans
6. **Add synchronize view** (2.1) — production recovery tool
7. **Implement install/uninstall handlers** (4.1, 4.2) — clean lifecycle

---

## SCOPE

- **Changes:** All files under `src/plone/typesense/` + new files as listed
- **Unchanged:** `pyproject.toml` dependencies (except adding optional redis), `CLAUDE.md`, test infrastructure layers in `testing.py` (extend, don't rewrite)

## ALTERNATIVES CONSIDERED

- **Rewrite from scratch using c.elasticsearch as template:** Rejected — plone.typesense has good architecture, just needs gap-filling. Typesense's API is fundamentally different from ES (no JSON DSL, filter strings instead), so a direct port wouldn't work.
- **Skip dynamic schema generation:** Rejected — static JSON schema is a major usability gap and source of errors. Dynamic generation from catalog indexes is essential for maintainability.
- **Skip Redis/async:** Accepted as Phase 5 optional — most Plone sites don't need async indexing, and Typesense is fast enough for synchronous operations.

---

## VERIFICATION

After each phase:
1. Run full test suite: `uv run pytest src/plone/typesense/tests/ -v`
2. Start Typesense: `docker compose up` or `./start-typesense.sh`
3. Start Plone, install plone.typesense
4. Manual testing:
   - Create/modify/delete content → verify Typesense reflects changes
   - Search with permissions → verify filtering works correctly
   - Rebuild catalog → verify Typesense rebuilds too
   - Check control panel sync status
5. For Phase 3+: test REST API endpoints via `curl`
6. Verify Typesense dashboard doc counts match Plone catalog
