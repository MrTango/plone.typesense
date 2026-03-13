# Gap Analysis: plone.typesense vs collective.elasticsearch — Roadmap to Final Version

## Context

plone.typesense is a Typesense integration for Plone modeled after collective.elasticsearch. While the core architecture (query routing, index adapters, result handling) is solid, many features present in the mature c.elasticsearch package are missing or incomplete. This analysis identifies every gap and proposes a phased roadmap to reach feature parity and production readiness.

---

## GAP ANALYSIS

### Legend
- **[MISSING]** — Not implemented at all
- **[STUB]** — Code exists but is non-functional
- **[PARTIAL]** — Partially implemented, needs completion
- **[OK]** — Implemented and equivalent

---

### 1. CATALOG PATCHING

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| searchResults patch | ✅ | ✅ | **[OK]** |
| __call__ patch | ✅ | ✅ | **[OK]** |
| unrestrictedSearchResults patch | ✅ | ✅ | **[OK]** |
| manage_catalogRebuild patch | ✅ Syncs ES during rebuild | ❌ | **[MISSING]** |
| manage_catalogClear patch | ✅ Clears both catalog + ES | ❌ | **[MISSING]** |
| uncatalog_object patch | ✅ Removes from ES on delete | ❌ | **[MISSING]** |
| moveObjectsByDelta patch | ✅ Reindexes position on reorder | ❌ | **[MISSING]** |

**Impact:** Without manage_catalogRebuild/Clear patches, catalog maintenance operations don't sync with Typesense. Without uncatalog_object, deletions may leave orphaned documents. Without moveObjectsByDelta, object reordering doesn't update positions in Typesense.

---

### 2. EVENT SUBSCRIBERS / CONTENT LIFECYCLE

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Object created → index | ✅ via IIndexQueueProcessor | ✅ via IndexProcessor | **[OK]** |
| Object modified → reindex | ✅ | ⚠️ Subscriber is stub (prints only) | **[STUB]** |
| Object deleted → unindex | ✅ via uncatalog_object patch | ❌ No delete handling | **[MISSING]** |
| Object moved/renamed → reindex | ✅ | ❌ | **[MISSING]** |
| Object copied → index | ✅ | ❌ | **[MISSING]** |
| Workflow transition → reindex | ✅ (via standard Plone events) | ❌ | **[MISSING]** |
| Transaction-aware queue | ✅ begin/commit/abort | ✅ begin/commit/abort | **[OK]** |

**Impact:** The subscriber stub at `subscribers/index_in_typesense.py` means content changes are NOT automatically synced to Typesense. This is a critical gap — currently only manual reindex works.

---

### 3. INDEX MANAGEMENT & MAPPING

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| MappingAdapter (schema from catalog) | ✅ Auto-generates ES mapping from catalog indexes | ❌ Schema is manually defined in JSON | **[MISSING]** |
| Versioned index naming | ✅ `{name}_{version}` | ✅ `{name}-{version}` aliases | **[OK]** |
| Index alias management | ✅ | ✅ | **[OK]** |
| Auto-detect index types from catalog | ✅ | ❌ Manual schema only | **[MISSING]** |
| convert_catalog_to_engine() | ✅ Initializes ES from existing catalog | ❌ | **[MISSING]** |

**Impact:** Without auto-schema generation, users must manually maintain the Typesense schema JSON when catalog indexes change. c.elasticsearch automatically derives the mapping from Plone's catalog configuration.

---

### 4. BROWSER VIEWS & MAINTENANCE TOOLS

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Control panel form | ✅ | ✅ | **[OK]** |
| Connection status display | ✅ cluster health, doc counts | ⚠️ test_connection only | **[PARTIAL]** |
| Convert catalog view | ✅ `@@elastic-convert` | ❌ | **[MISSING]** |
| Rebuild catalog view | ✅ `@@elastic-rebuild` | ⚠️ `@@typesense-reindex-collection` (basic) | **[PARTIAL]** |
| Synchronize view | ✅ `@@elastic-synchronize` (compare UIDs, reindex missing, delete orphans) | ❌ | **[MISSING]** |
| Data sync indicator | ✅ Shows doc count comparison | ❌ | **[MISSING]** |
| CSRF protection on views | ✅ | ❌ | **[MISSING]** |

**Impact:** The synchronize view is critical for production — it finds orphaned documents in Typesense and missing documents from Plone, then fixes discrepancies. Without it, data drift is hard to detect and fix.

---

### 5. REST API SERVICES

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Info endpoint | ✅ Returns ES cluster info | ❌ | **[MISSING]** |
| Convert action (REST) | ✅ POST convert | ❌ | **[MISSING]** |
| Rebuild action (REST) | ✅ POST rebuild | ❌ | **[MISSING]** |
| Control panel REST adapter | ✅ | ✅ | **[OK]** |

**Impact:** No REST API means remote management (e.g., from a CI/CD pipeline or monitoring tool) is not possible.

---

### 6. SEARCH FEATURES

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Full-text search | ✅ | ✅ | **[OK]** |
| Filter queries | ✅ | ✅ | **[OK]** |
| Sort support | ✅ | ✅ | **[OK]** |
| Highlighting | ✅ custom pre/post tags | ✅ basic highlighting | **[OK]** |
| Negation queries (`not`) | ✅ | ❌ | **[MISSING]** |
| Phrase matching / boost | ✅ ZCTextIndex phrase matching | ❌ | **[MISSING]** |
| Custom search view | ✅ Overrides munge_search_term | ❌ | **[MISSING]** |
| Faceted search / aggregations | ✅ (via ES aggregations) | ⚠️ Fields marked facet:true but no aggregation API | **[PARTIAL]** |

**Impact:** Negation queries (`not: [value]`) and phrase matching are used by advanced Plone search. The custom search view prevents Plone from mangling search terms.

---

### 7. ASYNC / QUEUE PROCESSING

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Synchronous bulk indexing | ✅ | ✅ | **[OK]** |
| Redis/RQ async queue (optional) | ✅ Two priority queues, retry logic | ❌ | **[MISSING]** |
| Binary file indexing (attachments) | ✅ via ES ingest-attachment plugin | ❌ | **[MISSING]** |
| Retry logic for failed operations | ✅ max=3, 30s intervals | ❌ | **[MISSING]** |

**Impact:** Redis queue support is important for high-traffic sites to avoid blocking requests during indexing. File content indexing enables searching inside PDFs, DOCX, etc.

---

### 8. ERROR HANDLING & RESILIENCE

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Fallback to catalog on error | ✅ | ✅ | **[OK]** |
| Configurable raise_exception | ✅ | ✅ | **[OK]** |
| IReindexActive marker | ✅ Prevents recursion during reindex | ❌ | **[MISSING]** |
| Per-field error handling during index | ✅ | ✅ | **[OK]** |
| Connection retry / sniffing | ✅ sniff_on_start, retry_on_timeout | ❌ | **[MISSING]** |

---

### 9. UPGRADES & MIGRATION

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| GenericSetup upgrade steps | ✅ upgrades.py with update_registry() | ❌ | **[MISSING]** |
| Profile versioning | ✅ Version 4 (with history) | Version 1000 (no upgrades) | **[MISSING]** |
| Post-install handler | ✅ Functional | ⚠️ Empty stub | **[STUB]** |
| Uninstall handler | ✅ Cleanup | ⚠️ Empty stub | **[STUB]** |

---

### 10. TESTING

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Search tests | ✅ 15KB+ comprehensive | ✅ ~568 lines real search | **[PARTIAL]** |
| Processor/indexing tests | ✅ 7.8KB | ❌ No dedicated processor tests | **[MISSING]** |
| Control panel tests | ✅ | ❌ | **[MISSING]** |
| REST API tests | ✅ | ❌ | **[MISSING]** |
| Redis integration tests | ✅ 9.7KB | N/A | N/A |
| Permission filtering tests | ✅ | ❌ | **[MISSING]** |
| Delete/unindex tests | ✅ | ❌ | **[MISSING]** |
| Rename/move tests | ✅ | ❌ | **[MISSING]** |
| Test cleanup (teardown) | ✅ Index+alias cleanup | ⚠️ Basic | **[PARTIAL]** |

---

### 11. CODE QUALITY & PRODUCTION READINESS

| Feature | c.elasticsearch | plone.typesense | Status |
|---------|----------------|-----------------|--------|
| Clean logging (no print statements) | ✅ | ❌ Many print() throughout | **[MISSING]** |
| Type hints | Partial | ❌ | **[MISSING]** |
| Proper CHANGES.rst | ✅ | ❌ | **[MISSING]** |
| PyPI release ready | ✅ | ❌ | **[MISSING]** |
| CI/CD pipeline | ✅ | ❌ | **[MISSING]** |

---

## ROADMAP

### Phase 0: Foundation & Stabilization (Priority: CRITICAL)
*Goal: Make the existing code actually work end-to-end*

| # | Task | Files | Est. |
|---|------|-------|------|
| 0.1 | **Fix event subscriber** — Replace stub with real implementation that calls IndexProcessor for index/reindex/unindex | `subscribers/index_in_typesense.py`, `subscribers/configure.zcml` | S |
| 0.2 | **Add missing lifecycle subscribers** — object deleted, moved, renamed, copied, workflow transition | `subscribers/configure.zcml`, `subscribers/index_in_typesense.py` | M |
| 0.3 | **Replace print() with logger** throughout entire codebase | All .py files | S |
| 0.4 | **Run and fix test suite** — establish green baseline | `tests/` | M |
| 0.5 | **Add uncatalog_object patch** — delete from Typesense when object removed | `patches/__init__.py`, `patches/configure.zcml` | S |

### Phase 1: Catalog Sync & Maintenance (Priority: HIGH)
*Goal: Keep Typesense and Plone catalog in sync reliably*

| # | Task | Files | Est. |
|---|------|-------|------|
| 1.1 | **Add manage_catalogRebuild patch** — sync Typesense during catalog rebuild | `patches/__init__.py` | S |
| 1.2 | **Add manage_catalogClear patch** — clear Typesense when catalog cleared | `patches/__init__.py` | S |
| 1.3 | **Add moveObjectsByDelta patch** — reindex positions on reorder | `patches/__init__.py` | S |
| 1.4 | **Add IReindexActive marker** — prevent recursion during bulk operations | `interfaces.py`, `patches/__init__.py` | S |
| 1.5 | **Implement synchronize view** — compare UIDs between Plone and Typesense, reindex missing, delete orphans | `views/typesense_synchronize.py` (new), `views/configure.zcml` | L |
| 1.6 | **Implement convert catalog view** — initialize Typesense from existing catalog | `views/typesense_convert.py` (new), `views/configure.zcml` | M |
| 1.7 | **Improve reindex view** — add progress tracking, CSRF protection, batch commits | `views/typesense_reindex_collection.py` | M |
| 1.8 | **Add data sync indicator to control panel** — show doc count comparison | `controlpanels/typesense_controlpanel/controlpanel.py` | S |

### Phase 2: Search Feature Parity (Priority: HIGH)
*Goal: Support all query types that c.elasticsearch handles*

| # | Task | Files | Est. |
|---|------|-------|------|
| 2.1 | **Add negation query support** (`not` operator in filters) | `indexes.py`, `query.py` | M |
| 2.2 | **Add phrase matching / boost for ZCTextIndex** | `indexes.py` | M |
| 2.3 | **Add custom search view** — prevent Plone from mangling search terms | `browser/search.py` (new), `browser/configure.zcml` | S |
| 2.4 | **Implement faceted search / aggregations API** — expose Typesense facet counts | `manager.py`, `result.py` | L |
| 2.5 | **Improve highlighting** — configurable pre/post tags in control panel | `controlpanels/`, `manager.py` | S |

### Phase 3: Schema Management (Priority: MEDIUM)
*Goal: Auto-derive schema, reduce manual configuration*

| # | Task | Files | Est. |
|---|------|-------|------|
| 3.1 | **Implement MappingAdapter equivalent** — auto-generate Typesense schema from catalog indexes | `mapping.py` (new) | L |
| 3.2 | **Add convert_catalog_to_typesense()** — initialize collection schema from catalog state | `manager.py` or `mapping.py` | M |
| 3.3 | **Schema diff detection** — detect when catalog indexes change and warn user | `controlpanels/` | M |

### Phase 4: REST API & Remote Management (Priority: MEDIUM)
*Goal: Enable programmatic management*

| # | Task | Files | Est. |
|---|------|-------|------|
| 4.1 | **Add Typesense info REST endpoint** — return connection status, doc count, collection info | `services/typesense.py` (new), `services/configure.zcml` (new) | M |
| 4.2 | **Add convert/rebuild REST actions** | `services/typesense.py` | M |
| 4.3 | **Add synchronize REST action** | `services/typesense.py` | S |

### Phase 5: Testing & Quality (Priority: HIGH — runs parallel to other phases)
*Goal: Comprehensive test coverage matching c.elasticsearch*

| # | Task | Files | Est. |
|---|------|-------|------|
| 5.1 | **Add IndexProcessor tests** — index, reindex, unindex, blob handling | `tests/test_processor.py` (new) | L |
| 5.2 | **Add permission filtering tests** — allowedRolesAndUsers, effectiveRange | `tests/test_permissions.py` (new) | M |
| 5.3 | **Add delete/unindex tests** — verify documents removed from Typesense | `tests/test_unindex.py` (new) | M |
| 5.4 | **Add rename/move tests** — verify path updates in Typesense | `tests/test_move_rename.py` (new) | M |
| 5.5 | **Add control panel tests** — settings persistence, connection test, rebuild | `tests/test_controlpanel.py` (new) | M |
| 5.6 | **Add synchronize view tests** | `tests/test_synchronize.py` (new) | M |
| 5.7 | **Improve test teardown** — clean up collections and aliases between tests | `testing.py` | S |

### Phase 6: Upgrades & Installation (Priority: MEDIUM)
*Goal: Clean install/uninstall/upgrade path*

| # | Task | Files | Est. |
|---|------|-------|------|
| 6.1 | **Implement post_install handler** — initialize collection on first install | `setuphandlers.py` | S |
| 6.2 | **Implement uninstall handler** — clean up Typesense collection | `setuphandlers.py` | S |
| 6.3 | **Add GenericSetup upgrade steps** — registry migration between versions | `upgrades.py` (new), `configure.zcml` | M |
| 6.4 | **Set proper profile versioning** — start from version 1, add upgrade path | `profiles/default/metadata.xml` | S |

### Phase 7: Production Readiness (Priority: MEDIUM)
*Goal: Ready for PyPI release*

| # | Task | Files | Est. |
|---|------|-------|------|
| 7.1 | **Add CHANGES.rst** | `CHANGES.rst` (new) | S |
| 7.2 | **Add connection resilience** — retry on timeout, configurable retries | `global_utilities/typesense.py`, `controlpanels/` | M |
| 7.3 | **Add CI/CD pipeline** — GitHub Actions for tests on push | `.github/workflows/` (new) | M |
| 7.4 | **Cleanup debug code** — remove all development print statements | All .py files | S |
| 7.5 | **PyPI packaging verification** — ensure sdist/wheel builds cleanly | `pyproject.toml` | S |

### Phase 8: Advanced Features (Priority: LOW — post-release)
*Goal: Go beyond c.elasticsearch parity*

| # | Task | Files | Est. |
|---|------|-------|------|
| 8.1 | **Async queue support** — optional celery/RQ integration for background indexing | `async/` (new package) | XL |
| 8.2 | **Binary file content indexing** — extract text from PDF/DOCX via Typesense or external pipeline | `queueprocessor.py` | XL |
| 8.3 | **Scoped API tokens** — per-user search tokens with embedded filters | `manager.py`, `controlpanels/` | L |
| 8.4 | **Typesense analytics integration** — search analytics, popular queries | New module | L |
| 8.5 | **Synonym support** — configurable synonym lists | `controlpanels/` | M |
| 8.6 | **Semantic/vector search** — leverage Typesense's vector search capabilities | New module | XL |

---

## SIZE LEGEND

| Size | Meaning |
|------|---------|
| S | Small — < 2 hours, single file change |
| M | Medium — 2-6 hours, 2-3 files |
| L | Large — 1-2 days, multiple files + tests |
| XL | Extra Large — 3+ days, new subsystem |

---

## SUGGESTED EXECUTION ORDER

**Sprint 1 (Weeks 1-2):** Phase 0 (all) + Phase 5.1 + Phase 5.7
- *Outcome: Working event subscribers, clean logging, green tests*

**Sprint 2 (Weeks 3-4):** Phase 1 (all) + Phase 5.2-5.6
- *Outcome: Full catalog sync, maintenance views, comprehensive tests*

**Sprint 3 (Weeks 5-6):** Phase 2 (all) + Phase 6 (all)
- *Outcome: Search feature parity, proper install/upgrade path*

**Sprint 4 (Weeks 7-8):** Phase 3 + Phase 4 + Phase 7
- *Outcome: Auto-schema, REST API, production-ready release*

**Post-release:** Phase 8 items as prioritized by users

---

## CRITICAL PATH

The absolute minimum to reach a usable v1.0:

1. **Fix event subscriber** (0.1, 0.2) — without this, nothing auto-indexes
2. **Add uncatalog_object patch** (0.5) — without this, deletes leave orphans
3. **Run and fix tests** (0.4) — establish confidence
4. **Add synchronize view** (1.5) — production recovery tool
5. **Clean up print statements** (0.3) — production logging
6. **Implement install/uninstall handlers** (6.1, 6.2) — clean lifecycle

Everything else adds polish and feature parity but these 6 items are blockers for any production use.

---

## VERIFICATION

After implementing each phase:
1. Run full test suite: `uv run pytest tests/ -v`
2. Start Typesense via `docker compose up`
3. Start Plone, install plone.typesense
4. Create/edit/delete content — verify Typesense stays in sync
5. Search via Plone UI — verify results match expectations
6. Check Typesense dashboard for document counts matching Plone catalog
