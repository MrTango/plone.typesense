# plone.typesense — Implementation Status

_Last updated: 2026-03-16_

## Phase 0: Critical Bug Fixes — "Make it actually work"

**Status: COMPLETE**

All 16 tasks implemented, 20 new tests added and passing, 28 existing tests still passing.

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 0.1 | Fix `check_perms` — remove hardcoded `False` | DONE | `manager.py` |
| 0.2 | Fix fallback to use restricted search when `check_perms=True` | DONE | `manager.py` (fixed by 0.1) |
| 0.3 | Implement `unindex()` — queue delete action | DONE | `queueprocessor.py` |
| 0.4 | Add "delete" branch to `commit_ts()` + `ts_delete()` method | DONE | `queueprocessor.py` |
| 0.5 | Fix `delete()` filter syntax | DONE | `global_utilities/typesense.py` |
| 0.6 | Fix `json.dumps()` — pass dicts, not strings | DONE | `global_utilities/typesense.py` |
| 0.7 | Fix reindex view: remove `self.index()`, fix double-indexing | DONE | `views/typesense_reindex_collection.py` |
| 0.8 | Fix `TypesenseResult.__getitem__` slice: `.end` → `.stop` | DONE | `result.py` |
| 0.9 | Fix brain highlighting: attribute assignment | DONE | `result.py` |
| 0.10 | Fix `TypesenseError` to inherit `Exception` | DONE | `global_utilities/typesense.py` |
| 0.11 | Fix `log.info(f"object: {object}")` → `obj` | DONE | `global_utilities/typesense.py` |
| 0.12 | Enable bulk import via `documents.import_()` | DONE | `global_utilities/typesense.py` |
| 0.13 | Extract `HTMLStripper` to module-level | DONE | `indexes.py` |
| 0.14 | Replace `print()`/`pprint()` with logging | DONE | `manager.py`, `queueprocessor.py`, `result.py`, `patches/__init__.py`, `subscribers/index_in_typesense.py` |
| 0.15 | Consolidate `MockIndex` to single location | DONE | `query.py` (canonical), `queueprocessor.py` (imports) |
| 0.16 | Add tests for all critical fixes | DONE | `tests/test_indexing_pipeline.py` (new, 20 tests) |

---

## Phase 1: Catalog Lifecycle — "Keep Typesense in sync"

**Status: COMPLETE**

All 8 tasks implemented, 45 new tests added and passing.

| # | Task | Status | Files Changed |
|---|------|--------|---------------|
| 1.1 | Event subscribers for content lifecycle (create/modify/delete/move/copy/workflow) | DONE | `subscribers/index_in_typesense.py`, `subscribers/configure.zcml` |
| 1.2 | `IReindexActive` marker interface | DONE | `interfaces.py` |
| 1.3 | Patch `uncatalog_object` — queue TS delete on object removal | DONE | `patches/__init__.py`, `patches/configure.zcml` |
| 1.4 | Patch `manage_catalogRebuild` — clear TS + rebuild | DONE | `patches/__init__.py`, `patches/configure.zcml` |
| 1.5 | Patch `manage_catalogClear` — clear TS collection | DONE | `patches/__init__.py`, `patches/configure.zcml` |
| 1.6 | `IAdditionalIndexDataProvider` interface + adapter lookup | DONE | `interfaces.py`, `queueprocessor.py` |
| 1.7 | Rewrite reindex view with CSRF protection + progress | DONE | `views/typesense_reindex_collection.py`, `views/configure.zcml`, `views/typesense_reindex_collection.pt` |
| 1.8 | Tests for patches, subscriber, reindex | DONE | `tests/test_catalog_lifecycle.py` (new, 45 tests) |

---

## Phase 2: Search Feature Parity & Maintenance Views

**Status: COMPLETE**

| # | Task | Status | Files |
|---|------|--------|-------|
| 2.1 | Synchronize view (UID comparison, index missing, delete orphans) | DONE | `views/` |
| 2.2 | Convert catalog view | DONE | `views/` |
| 2.3 | Negation query support | DONE | `indexes.py`, `query.py` |
| 2.4 | Phrase matching / boost for ZCTextIndex | DONE | `indexes.py` |
| 2.5 | Custom search view | DONE | `browser/` |
| 2.6 | Faceted search / aggregations API | DONE | `manager.py`, `result.py` |
| 2.7 | Data sync indicator in control panel | DONE | `controlpanels/` |
| 2.8 | Configurable highlighting | DONE | `controlpanels/`, `manager.py` |
| 2.9 | Permission filtering + search tests | DONE | `tests/` |

---

## Phase 3: Schema Management & REST API

**Status: COMPLETE**

| # | Task | Status | Files |
|---|------|--------|-------|
| 3.1 | MappingAdapter — auto-generate schema from catalog | DONE | `mapping.py` |
| 3.2 | `IMappingProvider` interface | DONE | `interfaces.py` |
| 3.3 | `convert_catalog_to_typesense()` | DONE | `manager.py` / `mapping.py` |
| 3.4 | Schema diff detection | DONE | `controlpanels/` |
| 3.5 | Typesense info REST endpoint | DONE | `services/` |
| 3.6 | Convert/rebuild/synchronize REST actions | DONE | `services/` |
| 3.7 | TypesenseFilterBuilder class | DONE | `filters.py` |
| 3.8 | Connection resilience (multi-node, retries, env-var fallback) | DONE | `global_utilities/typesense.py` |
| 3.9 | Tests for schema, REST, filter builder | DONE | `tests/` |

---

## Phase 4: Upgrades, Installation & Release

**Status: COMPLETE**

| # | Task | Status | Files |
|---|------|--------|-------|
| 4.1 | Post-install handler | DONE | `setuphandlers.py` |
| 4.2 | Uninstall handler | DONE | `setuphandlers.py` |
| 4.3 | GenericSetup upgrade steps | DONE | `upgrades.py` |
| 4.4 | Profile versioning | DONE | `profiles/default/metadata.xml` |
| 4.5 | CHANGES.rst | DONE | `CHANGES.rst` |
| 4.6 | CI/CD pipeline | DONE | `.github/workflows/` |
| 4.7 | PyPI packaging verification | DONE | `pyproject.toml` |

---

## Refactoring Cleanup (Sprints 1–4)

**Status: COMPLETE**

Full Elasticsearch-to-Typesense refactoring and dead code removal. 441 tests passing, zero ES references, zero TODOs in production code (except one low-priority note in controlpanel.py:285), zero print() in production code.

| Sprint | Scope | Status |
|--------|-------|--------|
| Sprint 1 | Remove QueryAssembler, get_query() methods, getIndex aliases | DONE |
| Sprint 2 | Remove dict path fallback, create_mapping(), extract() methods | DONE |
| Sprint 3 | Remove backward-compat aliases, dead imports, unused helpers | DONE |
| Sprint 4 | Final audit, STATUS.md update, release preparation | DONE |
| Sprint 5 | Dependency hardening, v1.0a2 release prep | DONE |
| Sprint 6 | Fix admin views, plone.restapi dependency, catalog search bypass | DONE |
| Sprint 7 | Fix search fallback bug, test isolation, remove legacy build files | DONE |

---

## Phase 5: Advanced Features (Post-release)

**Status: PARTIALLY COMPLETE**

| # | Task | Priority | Status |
|---|------|----------|--------|
| 5.1 | Async queue support (Redis/RQ) | LOW | TODO |
| 5.2 | Blob text extraction (PDF/DOCX) | MEDIUM | DONE |
| 5.3 | Patch `moveObjectsByDelta` | LOW | DONE |
| 5.4 | Scoped API tokens | LOW | DONE |
| 5.5 | Synonym support | LOW | DONE |
| 5.6 | Semantic/vector search | LOW | TODO |
