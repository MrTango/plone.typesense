# plone.typesense - TODO List

**Last Updated:** 2025-10-06
**Branch:** refac1

---

## 🔴 Critical Priority

### Run and Verify Test Suite

- [ ] **Execute full test suite**
  - Run: `../../bin/test -s plone.typesense`
  - Document total test count
  - Document pass/fail rate
  - Create baseline for future work

- [ ] **Analyze test results**
  - If failures exist: categorize by type (indexing, querying, setup)
  - Identify patterns in failures
  - Document in memories/TEST_RESULTS_YYYY_MM_DD.md

- [ ] **Fix any failing tests** (if needed)
  - Run failing tests individually with verbose output
  - Debug root causes (not symptoms)
  - Verify fixes don't break other tests

---

## 🟠 High Priority

### Verify Core Functionality

- [ ] **Test with real Typesense server**
  - Start Typesense: `podman-compose up` or `docker-compose up`
  - Create test Plone site
  - Add documents and verify indexing
  - Perform searches and verify results

- [ ] **Verify SearchableText extraction**
  - Create document with rich body text
  - Query Typesense directly to inspect document
  - Confirm SearchableText field contains: Title + Description + body text
  - Verify HTML tags are stripped

- [ ] **Test query scenarios**
  - Simple text search: `SearchableText='foo'`
  - Title search: `Title='Document Title'`
  - Combined filters: `portal_type='Document' + SearchableText='foo'`
  - Date ranges
  - Permission filtering

### Testing & Quality

- [ ] **Add missing test coverage** (after baseline established)
  - Edge cases in query conversion
  - Special characters in filter values
  - Complex filter combinations
  - Empty result handling

### Documentation

- [ ] **Add comprehensive docstrings**
  - All public methods in manager.py
  - All public methods in query.py
  - Index adapter classes

- [ ] **Create troubleshooting guide**
  - Common error messages
  - Debugging techniques
  - Performance tuning tips

- [ ] **Document query patterns**
  - Examples of common queries
  - Typesense filter syntax reference
  - Migration from catalog queries

---

## 🟡 Medium Priority

### Code Quality

- [ ] **Refactor filter building**
  - Replace string concatenation with builder pattern
  - Add proper escaping for all special characters
  - Add query validation before sending to Typesense

- [ ] **Improve error handling**
  - Better error messages with context
  - Graceful degradation on Typesense errors
  - Logging for debugging

- [ ] **Remove technical debt**
  - Replace MockIndex pattern with proper solution
  - Decouple Manager/QueryAssembler/Result classes
  - Add type hints throughout

### Features

- [ ] **Query caching**
  - Cache assembled queries
  - Cache Typesense responses
  - Configurable TTL

- [ ] **Collection management**
  - Collection versioning with aliases
  - Export/import for schema updates
  - Zero-downtime schema migrations

- [ ] **Batch operations**
  - Optimize bulk reindexing
  - Progress tracking for large operations
  - Resume interrupted reindexing

---

## 🟢 Low Priority

### Advanced Features

- [ ] **Scoped API tokens**
  - Generate user-specific tokens
  - Automatic token rotation
  - Token caching

- [ ] **Field-level permissions**
  - Separate collections for restricted fields
  - Dynamic schema based on user permissions

- [ ] **Typesense analytics**
  - Search analytics integration
  - Popular queries tracking
  - Performance metrics

- [ ] **Advanced text search**
  - Synonym support
  - Custom ranking rules
  - Semantic search integration

### Performance

- [ ] **Connection pooling**
  - Reuse Typesense client connections
  - Configure pool size
  - Monitor connection health

- [ ] **Indexing optimization**
  - Parallel indexing for large batches
  - Delta indexing (only changed fields)
  - Scheduled full reindex

- [ ] **Query optimization**
  - Query result caching
  - Prefetch related objects
  - Lazy brain loading improvements

---

## ✅ Completed

### Core Implementation
- [x] Convert query system from Elasticsearch to Typesense syntax
- [x] Implement monkey patches for catalog interception (patches/__init__.py)
- [x] Add permission filtering (allowedRolesAndUsers integration)
- [x] Implement lazy result loading (TypesenseResult)
- [x] Add support for all major index types (8 adapters)
- [x] Implement SearchableText body text extraction (TZCTextIndex)
- [x] Add HTML stripping for body text (HTMLParser implementation)
- [x] Implement field normalization for Typesense schema
- [x] Add ts_only_indexes support (MockIndex pattern)

### Testing Infrastructure
- [x] Create comprehensive test suite (11 test files, ~4000 lines)
- [x] Unit tests for query conversion
- [x] Unit tests for SearchableText extraction
- [x] Integration tests for indexing
- [x] Integration tests for searching
- [x] E2E test infrastructure

### Documentation
- [x] CLAUDE.md - Developer guide with architecture
- [x] STATUS.md - Current project status
- [x] TODOS.md - Task tracking
- [x] README.md - Basic project overview
- [x] memories/KEY_LEARNINGS.md - Development insights
- [x] memories/ARCHITECTURE_DIAGRAM.md - Visual diagrams

---

## 🗑️ Won't Do / Deferred

- Robot framework tests (replaced with unit/integration tests)
- Elasticsearch compatibility layer (pure Typesense implementation)

---

## Notes

### Current Development Phase
**Phase:** Testing & Verification
- Implementation is complete
- Need to run tests to establish baseline
- Then fix any issues found
- Then move to production readiness

### Testing Strategy
1. **First:** Run full test suite, establish baseline
2. **Second:** Manual testing with real Typesense server
3. **Third:** Fix any issues found
4. **Fourth:** Add missing edge case tests
5. **Fifth:** Performance testing

### Code Review Checklist (for future PRs)
- [ ] All tests passing
- [ ] Docstrings added for public APIs
- [ ] Type hints added (where applicable)
- [ ] Error handling with fallback to catalog
- [ ] Performance considerations addressed
- [ ] Backwards compatibility maintained
- [ ] No hardcoded values (use registry)

### Release Checklist (when ready)
- [ ] All tests passing (95%+ pass rate)
- [ ] Documentation complete
- [ ] CHANGES.rst updated
- [ ] Version bumped appropriately
- [ ] Migration guide written (if needed)
- [ ] Manual testing with real Plone site completed
- [ ] Performance benchmarks documented
