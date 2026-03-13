# splan: Gap Analysis & Roadmap -- plone.typesense vs collective.elasticsearch

## Goal

Deep gap analysis between plone.typesense and the collective.elasticsearch reference implementation, with a phased roadmap to reach full feature parity and production readiness.

## Context

plone.typesense has a solid architectural foundation (query routing, index adapters, result handling) but has **critical bugs** (permission filtering disabled, unindex is a no-op, delete syntax wrong, json.dumps passed where dicts expected) and **missing features** compared to collective.elasticsearch (no catalog lifecycle patches, no sync view, no dynamic schema, stub event subscriber). This roadmap addresses all gaps from critical bugs through to final version.

---

## Critical Bugs (Fix BEFORE any roadmap work)

These are **broken code**, not missing features:

| Bug | File:Line | Issue |
|-----|-----------|-------|
| **Permission filtering disabled** | `manager.py:183` | `check_perms = False` hardcoded -- every search is unrestricted (OWASP A01:2021) |
| **Fallback also unrestricted** | `manager.py:209-213` | On Typesense error, fallback always uses `_old_unrestrictedSearchResults` because `check_perms` is forced False |
| **unindex() is a no-op** | `queueprocessor.py:384-388` | Only prints, never queues delete action |
| **commit_ts() ignores deletes** | `queueprocessor.py:416-420` | Only handles "index" and "update", no "delete" branch |
| **delete() wrong filter syntax** | `global_utilities/typesense.py:193-194` | `{"filter_by=id": uids}` is invalid; should be `{"filter_by": "id:[uid1,uid2]"}` |
| **json.dumps() passed to Typesense client** | `global_utilities/typesense.py:158,166` | `upsert(json.dumps(obj))` and `update(json.dumps(obj))` pass JSON strings where Typesense Python client expects dicts -- entire indexing pipeline is broken |
| **Reindex view crashes** | `views/typesense_reindex_collection.py:40` | `return self.index()` -- no such method exists, always `AttributeError` |
| **Reindex view double-indexing** | `views/typesense_reindex_collection.py:36-37` | `if len(self.objects) > 0` check inside loop callback causes partial re-indexing on every batch |
| **TypesenseResult slice crash** | `result.py:175` | `range(key.start, key.end)` -- Python slices have `.stop`, not `.end` |
| **Brain highlighting crash** | `result.py:104` | `brain["Description"] = ...` -- neither TypesenseBrain nor catalog brains support `__setitem__` |
| **TypesenseError(BaseException)** | `global_utilities/typesense.py:10` | Inherits `BaseException` not `Exception` -- won't be caught by `except Exception` blocks |
| **Logging uses `object` builtin** | `global_utilities/typesense.py:157,165` | `log.info(f"object: {object}")` logs the builtin, not the `obj` variable |
| **Bulk import commented out** | `global_utilities/typesense.py:167-184` | Individual upserts in a loop instead of `documents.import_()` |
| **print() statements everywhere** | 9+ files, ~215 occurrences | Debug prints instead of `log.debug()`, includes `from pprint import pprint` |

---

## Gap Analysis Summary

### A. Missing Features (17 gaps)

| ID | Feature | c.elasticsearch | plone.typesense | Priority |
|----|---------|-----------------|-----------------|----------|
| A1 | Dynamic schema generation | `mapping.py` MappingAdapter | Static JSON in control panel | HIGH |
| A2 | IAdditionalIndexDataProvider | Interface + adapter lookup | Commented-out code in queueprocessor | HIGH |
| A3 | IMappingProvider interface | External schema contributions | None | MEDIUM |
| A4 | Synchronize view (bidirectional) | `utilviews.py` synchronize() | Only one-way reindex (broken) | HIGH |
| A5 | Convert catalog view | `utilviews.py` convert() | None | MEDIUM |
| A6 | manage_catalogRebuild patch | Intercepts rebuild, flags reindexing | Not patched | HIGH |
| A7 | manage_catalogClear patch | Clears ES before original | Not patched | HIGH |
| A8 | uncatalog_object patch | Extends removal to ES | Not patched | CRITICAL |
| A9 | moveObjectsByDelta patch | Reindexes on reorder | Not patched | LOW |
| A10 | Redis/async processing | Full redis/ module with queues | None | LOW |
| A11 | REST API service endpoints | Info GET + Maintenance POST | None | MEDIUM |
| A12 | IReindexActive marker | Prevents recursive operations | Referenced in comment only | HIGH |
| A13 | Upgrade steps | upgrades.py | None | MEDIUM |
| A14 | Thread-local data management | local.py | None | LOW |
| A15 | Blob text extraction pipeline | Tika-based attachment pipeline | Metadata only, no text extraction | MEDIUM |
| A16 | flush_indices / refresh | Force searchable after index | None (less critical for Typesense) | LOW |
| A17 | Control panel sync status | Document count comparison | No sync indicator | MEDIUM |

### B. Partial Implementations (9 gaps)

| ID | Feature | Current State | What's Missing |
|----|---------|---------------|----------------|
| B1 | Event subscriber | Stub: prints event class | Must trigger IndexProcessor |
| B2 | unindex operation | Prints obj.id, returns | Must queue delete action |
| B3 | Bulk import | Individual upserts in loop | Use documents.import_() |
| B4 | clear_and_rebuild | Code commented out | Must walk portal + extract + send |
| B5 | Reindex view | Crashes (calls nonexistent method), sends raw objects | Complete rewrite needed |
| B6 | Permission filtering | check_perms hardcoded False | Must respect caller parameter + fix fallback |
| B7 | delete() filter syntax | Invalid filter format | Fix to valid Typesense syntax |
| B8 | Blob text extraction | Infrastructure exists, data unused | Wire into indexing pipeline |
| B9 | Debug prints | ~215 print() calls across 9 files | Replace with log.debug() |

### C. Quality/Robustness Gaps (9 gaps)

| ID | Area | Gap |
|----|------|-----|
| C1 | Error handling | Bare `except Exception` vs specific errors |
| C2 | MockIndex duplication | Defined inline in both queueprocessor.py:113 and query.py:67 with subtle differences |
| C3 | Filter building | String concatenation, no validation |
| C4 | Connection management | Single node, no retries |
| C5 | Catalog sync state | No way to know if Typesense is in sync |
| C6 | CSRF protection | Reindex view performs destructive ops on GET with no CSRF token |
| C7 | Test coverage | No tests for: indexing pipeline, unindexing, control panel, permissions |
| C8 | HTMLStripper duplication | Identical inner class at indexes.py:327 and indexes.py:383 |
| C9 | API key storage | Plain TextLine in registry, no env-var fallback or Password widget |

---

## Roadmap

### Phase 1: Critical Fixes -- "Make it actually work"
**Effort:** 3-4 days | **Depends on:** Nothing

| # | Task | Files to Modify |
|---|------|----------------|
| 1.1 | Fix `check_perms` -- remove hardcoded `False`, respect caller param | `manager.py:183` |
| 1.2 | Fix fallback to use restricted search when `check_perms=True` | `manager.py:209-213` |
| 1.3 | Implement `unindex()` -- add to `actions.unindex` dict | `queueprocessor.py:384-388` |
| 1.4 | Add "delete" branch to `commit_ts()` calling `ts_delete()` | `queueprocessor.py:416-420` |
| 1.5 | Fix `delete()` filter syntax to valid Typesense format | `global_utilities/typesense.py:186-195` |
| 1.6 | Fix `json.dumps()` -- pass dicts to Typesense client, not JSON strings | `global_utilities/typesense.py:158,166` |
| 1.7 | Fix `log.info(f"object: {object}")` to use `obj` variable | `global_utilities/typesense.py:157,165` |
| 1.8 | Fix `TypesenseError` to inherit `Exception` not `BaseException` | `global_utilities/typesense.py:10` |
| 1.9 | Enable bulk import via `documents.import_()`, keep upsert as fallback | `global_utilities/typesense.py:160-184` |
| 1.10 | Fix reindex view: remove `self.index()` call, fix double-indexing logic | `views/typesense_reindex_collection.py:36-40` |
| 1.11 | Fix `TypesenseResult.__getitem__` slice: `.end` -> `.stop` | `result.py:175` |
| 1.12 | Fix brain highlighting: use `setattr` or proper attribute assignment | `result.py:104` |
| 1.13 | Extract `HTMLStripper` to module-level, remove duplicate (C8) | `indexes.py:327,383` |
| 1.14 | Replace all `print()`/`pprint()` with `log.debug()`/`log.info()` | 9+ files |
| 1.15 | Add tests for all critical fixes | `tests/test_indexing_pipeline.py` (new) |

**Milestone: FUNCTIONAL** -- CRUD operations work end-to-end, permissions enforced, no crashes.

---

### Phase 2: Core Gaps -- "Match c.elasticsearch catalog lifecycle"
**Effort:** 5-7 days | **Depends on:** Phase 1

| # | Task | Files to Modify/Create |
|---|------|----------------------|
| 2.1 | Add `IReindexActive` marker interface (A12) | `interfaces.py` |
| 2.2 | Implement event subscriber (B1) -- trigger IndexProcessor on content events | `subscribers/index_in_typesense.py` |
| 2.3 | Patch `manage_catalogRebuild` (A6) -- clear TS, flag IReindexActive, rebuild, flush | `patches/__init__.py`, `patches/configure.zcml` |
| 2.4 | Patch `manage_catalogClear` (A7) -- clear TS collection before original | `patches/__init__.py`, `patches/configure.zcml` |
| 2.5 | Patch `uncatalog_object` (A8) -- queue TS delete on object removal | `patches/__init__.py`, `patches/configure.zcml` |
| 2.6 | Fix `clear_and_rebuild` control panel action (B4) -- implement full rebuild flow | `controlpanels/typesense_controlpanel/controlpanel.py` |
| 2.7 | Rewrite reindex view with IndexProcessor.get_data() + CSRF protection (B5, C6) | `views/typesense_reindex_collection.py` |
| 2.8 | Consolidate MockIndex to single location in `indexes.py` (C2) | `indexes.py`, `queueprocessor.py`, `query.py` |
| 2.9 | Add `IAdditionalIndexDataProvider` interface and wire adapter lookup (A2) | `interfaces.py`, `queueprocessor.py` |
| 2.10 | Add sync state tracking -- document count comparison (C5) | `manager.py` |
| 2.11 | Tests for patches, control panel, subscriber | `tests/test_patches.py`, `tests/test_controlpanel.py` (new) |

**Milestone: FEATURE PARITY** -- All catalog lifecycle operations handled correctly.

---

### Phase 3: Advanced Features -- "Production-grade"
**Effort:** 10-14 days | **Depends on:** Phase 2

| # | Task | Files to Modify/Create |
|---|------|----------------------|
| 3.1 | Dynamic schema generation via MappingAdapter (A1) | `mapping.py` (new) |
| 3.2 | `IMappingProvider` interface (A3) | `interfaces.py`, `configure.zcml` |
| 3.3 | Synchronize view -- bidirectional UID comparison, index missing, delete orphans (A4) | `views/typesense_sync.py` (new) |
| 3.4 | REST API service endpoints -- Info GET + Maintenance POST (A11) | `services/` package (new) |
| 3.5 | Enhanced control panel with sync status indicator (A17, C1) | `controlpanels/typesense_controlpanel/controlpanel.py` |
| 3.6 | Upgrade steps infrastructure (A13) | `upgrades.py` (new), `configure.zcml`, `profiles/default/metadata.xml` |
| 3.7 | TypesenseFilterBuilder class -- replace string concatenation (C3) | `filters.py` (new), update `indexes.py` |
| 3.8 | Connection resilience -- multi-node, retries, env-var API key (C4, C9) | `global_utilities/typesense.py` |
| 3.9 | Blob text extraction -- wire get_blob_data() into pipeline (A15, B8) | `queueprocessor.py` |
| 3.10 | Tests for all Phase 3 features | `tests/test_mapping.py`, `tests/test_sync.py`, `tests/test_services.py`, `tests/test_filter_builder.py` |

**Milestone: PRODUCTION-READY** -- Suitable for real deployments with admin tooling.

---

### Phase 4: Polish & Optional -- "Final version"
**Effort:** 5-7 days (incremental) | **Depends on:** Phase 3

| # | Task | Files to Modify/Create |
|---|------|----------------------|
| 4.1 | Async processing via Redis/RQ (A10) | `async/` package (new), conditional ZCML |
| 4.2 | Patch `moveObjectsByDelta` (A9) | `patches/__init__.py`, `patches/configure.zcml` |
| 4.3 | Thread-local data management for IndexProcessor (A14) | `local.py` (new) |
| 4.4 | Query caching with configurable TTL | `cache.py` (new) |
| 4.5 | GenericSetup dev profile | `profiles/docker-dev/` (new) |
| 4.6 | Performance benchmarks | `tests/test_performance.py` (new) |
| 4.7 | Comprehensive documentation | `docs/` |

**Milestone: FINAL VERSION** -- Complete feature parity + extras.

---

## Critical Analysis (by plan-critic agent)

### Plausibility
| Step | Finding | Severity |
|------|---------|----------|
| All critical bugs | All line numbers and code verified against actual source | Confirmed |
| Reindex view crash | `self.index()` at line 40 -- no such method exists, verified | Confirmed |
| json.dumps bug | Lines 158,166 pass JSON strings to Typesense client expecting dicts | Confirmed |
| print() count | ~215 occurrences across 9 files, plan originally said "dozens" | Low (underscoped) |

### Correctness
| Step | Finding | Severity |
|------|---------|----------|
| Fallback unrestricted | `manager.py:209-213` fallback always uses `_old_unrestrictedSearchResults` when `check_perms=False` -- doubles the permission bypass impact. **Added to Phase 1.** | **Critical** |
| json.dumps to client | Makes entire indexing pipeline non-functional. **Added to Phase 1.** | **High** |
| Reindex view crash | Always raises AttributeError. **Added to Phase 1.** | **High** |
| Slice .end vs .stop | `result.py:175` crashes on any slice access. **Added to Phase 1.** | **Medium** |
| brain["Description"] | Neither brain type supports `__setitem__`. **Added to Phase 1.** | **Medium** |
| Phase 1.3+1.4 coupling | unindex() and commit_ts() delete branch must both be fixed or deletes are queued but never executed | **Medium** |
| Phase 3 scope | Originally 7-10 days was optimistic for 10 tasks. **Revised to 10-14 days.** | **Medium** |

### Security
| Step | Finding | Severity |
|------|---------|----------|
| Permission bypass | check_perms=False + unrestricted fallback = complete access control bypass (OWASP A01:2021) | **Critical** |
| CSRF on reindex | Destructive reindexing on GET with no CSRF token | **High** |
| API key storage | Plain TextLine in registry, accessible to any Manager user | **Medium** |

### Codebase Hygiene
| Step | Finding | Severity |
|------|---------|----------|
| HTMLStripper duplication | Identical inner class at indexes.py:327 and :383. **Added to Phase 1.** | **Medium** |
| `enabled` property duplication | Both TypesenseManager and TypesenseConnector read same registry key independently | Low |
| Thread-local inconsistency | Connector uses threading.local() but IndexProcessor caches _ts_client as instance attr | Medium |
| Dead commented-out code | Substantial in 5+ files | Low |
| Unused `objects_for_bulk` variable | Lines 155 and 163 in typesense.py | Low |

## Revisions Made After Critical Analysis

1. **Added 8 new bugs** to Critical Bugs table (json.dumps, fallback unrestricted, reindex crashes, slice .end, brain setitem, BaseException, log object builtin, HTMLStripper dup)
2. **Phase 1 expanded** from 7 to 15 tasks to address all newly-found bugs
3. **Phase 3 effort revised** from 7-10 days to 10-14 days (realistic scope)
4. **Added C8 and C9** to Quality gaps (HTMLStripper duplication, API key storage)
5. **All CRITICAL and HIGH findings addressed** in the roadmap

## Verdict

**SAFE** -- All CRITICAL and HIGH findings have been incorporated into the roadmap. No unaddressed critical issues remain.

---

## Verification Plan

After each phase:
1. Run full test suite: `uv run pytest src/plone/typesense/tests/`
2. Start Typesense: `./start-typesense.sh`
3. Manual testing with real Plone site:
   - Create/modify/delete content -> verify Typesense reflects changes
   - Search with permissions -> verify filtering works
   - Rebuild catalog -> verify Typesense rebuilds too
   - Check control panel sync status
4. For Phase 3+: test REST API endpoints via `curl` or Postman

## Scope

- **Changes:** All files under `src/plone/typesense/` + new files as listed
- **Unchanged:** `pyproject.toml` dependencies (except adding optional redis), `CLAUDE.md`, test infrastructure layers in `testing.py` (extend, don't rewrite)

## Alternatives Considered

- **Rewrite from scratch using c.elasticsearch as template:** Rejected -- plone.typesense has good architecture, just needs gap-filling. Typesense's API is fundamentally different from ES (no JSON DSL, filter strings instead), so a direct port wouldn't work.
- **Skip dynamic schema generation:** Rejected -- static JSON schema is a major usability gap and source of errors. Dynamic generation from catalog indexes is essential for maintainability.
- **Skip Redis/async:** Accepted as Phase 4 optional -- most Plone sites don't need async indexing, and Typesense is fast enough for synchronous operations.
