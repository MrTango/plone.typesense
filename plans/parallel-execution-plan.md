# Parallelized Execution Plan — Phases 2-5

_Restructured from `gap-analyzis-improved-plan.md` for maximum parallelism._
_Phases 0 and 1 remain sequential as originally planned._

---

## Dependency Analysis Summary

The original plan chains phases 2→3→4→5 sequentially (~20-33 days). Analysis shows most tasks only depend on Phase 1 completing, not on each other. The true dependency bottleneck is **Group E (REST API)**, which wraps views and schema operations from other groups.

---

## Parallel Track Groups

All groups below can start **immediately after Phase 1 completes**, unless noted otherwise.

### Group A: Search Features + FilterBuilder
**Effort:** 5-7 days | **Depends on:** Phase 1

These tasks all touch query/search code (`indexes.py`, `query.py`, `manager.py`, `result.py`). The FilterBuilder (originally Phase 3) belongs here since it modifies the same files as negation/phrase support.

| # | Task | Original | Files |
|---|------|----------|-------|
| 2.3 | Negation query support (`!=` filter syntax) | Phase 2 | `indexes.py`, `query.py` |
| 2.4 | Phrase matching / boost for ZCTextIndex | Phase 2 | `indexes.py` |
| 2.5 | Custom search view (prevent term mangling) | Phase 2 | `browser/search.py` (new), `browser/configure.zcml` |
| 2.6 | Faceted search / aggregations API | Phase 2 | `manager.py`, `result.py` |
| 2.8 | Configurable highlighting (pre/post tags) | Phase 2 | `controlpanels/`, `manager.py` |
| 3.7 | TypesenseFilterBuilder class (replace string concat) | Phase 3 | `filters.py` (new), `indexes.py` |

**Internal ordering:** 3.7 (FilterBuilder) first, then 2.3/2.4 build on it. 2.5, 2.6, 2.8 are independent of each other.

---

### Group B: Maintenance Views
**Effort:** 3-4 days | **Depends on:** Phase 1

New views for operational use. Independent of search features.

| # | Task | Original | Files |
|---|------|----------|-------|
| 2.1 | Synchronize view (UID comparison, index missing, delete orphans) | Phase 2 | `views/typesense_sync.py` (new), `views/configure.zcml` |
| 2.2 | Convert catalog view (initialize TS from catalog) | Phase 2 | `views/typesense_convert.py` (new), `views/configure.zcml` |
| 2.7 | Data sync indicator in control panel (doc count comparison) | Phase 2 | `controlpanels/typesense_controlpanel/controlpanel.py` |

**Internal ordering:** 2.1 and 2.2 are independent. 2.7 can reuse sync logic from 2.1.

---

### Group C: Schema Management
**Effort:** 5-7 days | **Depends on:** Phase 1

Auto-generating Typesense schemas from Plone catalog indexes. No dependency on Phase 2 search features.

| # | Task | Original | Files |
|---|------|----------|-------|
| 3.1 | MappingAdapter — auto-generate schema from catalog indexes | Phase 3 | `mapping.py` (new) |
| 3.2 | `IMappingProvider` interface (external schema contributions) | Phase 3 | `interfaces.py`, `configure.zcml` |
| 3.3 | `convert_catalog_to_typesense()` — initialize collection from catalog state | Phase 3 | `manager.py` or `mapping.py` |
| 3.4 | Schema diff detection — warn when catalog indexes change | Phase 3 | `controlpanels/` |

**Internal ordering:** 3.1 → 3.2 → 3.3 → 3.4 (each builds on the previous).

---

### Group D: Infrastructure & Release Prep
**Effort:** 3-5 days | **Depends on:** Phase 1

Connection resilience, install/uninstall lifecycle, upgrade steps, CI/CD, packaging. All independent of search features, views, and schema work.

| # | Task | Original | Files |
|---|------|----------|-------|
| 3.8 | Connection resilience (multi-node, retries, env-var API key fallback) | Phase 3 | `global_utilities/typesense.py`, `controlpanels/` |
| 4.1 | Post-install handler (initialize collection on install) | Phase 4 | `setuphandlers.py` |
| 4.2 | Uninstall handler (clean up TS collection) | Phase 4 | `setuphandlers.py` |
| 4.3 | GenericSetup upgrade steps | Phase 4 | `upgrades.py` (new), `configure.zcml` |
| 4.4 | Profile versioning (start from version 1) | Phase 4 | `profiles/default/metadata.xml` |
| 4.6 | CI/CD pipeline (GitHub Actions) | Phase 4 | `.github/workflows/` (new) |
| 4.7 | PyPI packaging verification | Phase 4 | `pyproject.toml` |

**Internal ordering:** 4.1/4.2 together. 4.3/4.4 together. 3.8, 4.6, 4.7 independent.

---

### Group E: REST API
**Effort:** 3-4 days | **Depends on:** Groups B + C

REST endpoints wrap the views (Group B) and schema operations (Group C), so this group must wait for both to complete.

| # | Task | Original | Files |
|---|------|----------|-------|
| 3.5 | Typesense info REST endpoint (connection status, doc count, collection info) | Phase 3 | `services/typesense.py` (new), `services/configure.zcml` (new) |
| 3.6 | Convert/rebuild/synchronize REST actions | Phase 3 | `services/typesense.py` |

**Internal ordering:** 3.5 first (info endpoint), then 3.6 (action endpoints that call sync/convert views).

---

### Group F: Tests & Documentation
**Effort:** 3-4 days | **Depends on:** Groups A-E

Tests for each group should be written alongside development, but comprehensive integration tests and documentation come after all groups land.

| # | Task | Original | Files |
|---|------|----------|-------|
| 2.9 | Permission filtering + advanced search tests | Phase 2 | `tests/test_permissions.py`, `tests/test_search_advanced.py` (new) |
| 3.9 | Schema, REST API, filter builder tests | Phase 3 | `tests/test_mapping.py`, `tests/test_services.py`, `tests/test_filter_builder.py` (new) |
| 4.5 | CHANGES.rst (summarizes all changes) | Phase 4 | `CHANGES.rst` (new) |

**Note:** Unit tests for individual tasks should be written within each group. Group F covers integration and cross-cutting tests.

---

### Group G: Advanced Features (Post-release)
**Effort:** Varies | **Depends on:** Groups A-F complete (v1.0 released)

All items are independent of each other and can be prioritized individually.

| # | Task | Priority |
|---|------|----------|
| 5.1 | Async queue support (Redis/RQ) | LOW |
| 5.2 | Blob text extraction (PDF/DOCX) | MEDIUM |
| 5.3 | Patch `moveObjectsByDelta` | LOW |
| 5.4 | Scoped API tokens | LOW |
| 5.5 | Synonym support | LOW |
| 5.6 | Semantic/vector search | LOW |

---

## Execution Timeline

```
Phase 0 (done)  ████████████████████████████████████████████
Phase 1         ████████████████████████████████████████████
                ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                   Sprint N (after Phase 1)    Sprint N+1
                ├──────────────────────────┤├──────────────┤
Track 1:        [A: Search + FilterBuilder ]
Track 2:        [B: Maint. Views  ]         [E: REST API  ]
Track 3:        [C: Schema Mgmt   ]         [E: REST API  ]
Track 4:        [D: Infrastructure & Release Prep         ]
                                             [F: Tests/Docs]
                ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
Post-release:   [G: Advanced features, individually prioritized]
```

### Sprint N (immediately after Phase 1) — ~7-10 days
- **Track 1:** Group A (Search + FilterBuilder)
- **Track 2:** Group B (Maintenance Views)
- **Track 3:** Group C (Schema Management)
- **Track 4:** Group D (Infrastructure & Release Prep)

### Sprint N+1 — ~5-7 days
- **Track 1:** Group E (REST API) — once B + C are done
- **Track 2:** Group F (Integration tests + CHANGES.rst)
- **Track 3:** Remaining Group D items if any spill over

### Post-release
- Group G items as prioritized by users

---

## Timeline Comparison

| Approach | Estimated Duration (after Phase 1) |
|----------|-----------------------------------|
| Original sequential (Phase 2→3→4→5) | 23-33 days |
| Parallelized (this plan) | 12-17 days |
| **Savings** | **~40-50%** |

---

## Risk Notes

- **File conflicts between tracks:** Groups A and C both touch `indexes.py` and `manager.py`. Coordinate merges or assign to same developer.
- **Group E is the bottleneck:** REST API can't start until Groups B and C complete. If either slips, E slips too.
- **Test coverage:** Each group should write unit tests alongside implementation. Group F is for integration and cross-cutting tests only.
