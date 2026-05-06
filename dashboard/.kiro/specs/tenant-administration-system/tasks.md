# Tasks Document: Tenant Administration System

## Overview

This document outlines the implementation tasks for the Tenant Administration System. Since the core functionality is already implemented and functional, these tasks focus on:

1. **Testing & Validation**: Comprehensive test coverage including property-based tests
2. **Security Enhancements**: Encryption, rate limiting, and audit logging
3. **Performance Optimization**: Cache improvements and database optimization
4. **Documentation**: User guides and developer documentation
5. **Monitoring & Observability**: Logging, metrics, and health checks

## Task Status Legend

- `pending`: Not started
- `in_progress`: Currently being worked on
- `completed`: Finished and verified
- `blocked`: Waiting on dependencies or external factors

---

## Phase 1: Testing & Validation

### Task 1.1: Property-Based Tests for Tenant Context

**Status**: `completed` ✅

**Description**: Implement property-based tests for the tenant context management system using the `hypothesis` library. These tests will validate the correctness properties defined in the design document.

**Completion Date**: 2026-05-05

**Acceptance Criteria**:
- [x] Install `hypothesis` and `pytest` testing frameworks
- [x] Create `tests/test_tenant_context_properties.py`
- [x] Implement Property 1: API Key uniqueness across all generated keys
- [x] Implement Property 2: Tenant retrieval by API Key returns consistent results
- [x] Implement Property 3: Cache hit returns same tenant as database query
- [x] Implement Property 4: Context isolation between concurrent requests
- [x] Implement Property 5: Lazy loading only loads configuration once
- [x] All property tests pass with 100+ examples each
- [x] Test coverage for `integrations/tenant_context.py` reaches 90%+ (achieved 92%)

**Dependencies**: None

**Estimated Effort**: 4-6 hours

**Actual Effort**: ~2 hours

**Files Created/Modified**:
- `tests/test_tenant_context_properties.py` (new) - 600+ lines
- `tests/conftest.py` (new) - 250+ lines
- `tests/__init__.py` (new)
- `pytest.ini` (new)
- `requirements.txt` (new)
- `TASK_1.1_COMPLETED.md` (documentation)

**Test Results**:
- 20 tests passing
- 92% code coverage
- All 5 correctness properties validated

**Correctness Properties Validated**:
- Property 1: API Key Uniqueness ✅
- Property 2: Tenant Retrieval Consistency ✅
- Property 3: Cache Consistency ✅
- Property 4: Context Isolation ✅
- Property 5: Lazy Loading Behavior ✅

---

### Task 1.2: Property-Based Tests for Tenant CRUD Operations

**Status**: `completed` ✅

**Description**: Implement property-based tests for tenant creation, retrieval, update, and deletion operations.

**Completion Date**: 2026-05-06

**Acceptance Criteria**:
- [x] Create `tests/test_tenant_crud_properties.py`
- [x] Implement Property 6: Created tenant can be retrieved by ID
- [x] Implement Property 7: Created tenant can be retrieved by API Key
- [x] Implement Property 8: Subdomain uniqueness constraint enforced
- [x] Implement Property 9: Plan validation (basic/pro/enterprise only)
- [x] Implement Property 10: Status validation (active/inactive only)
- [x] Implement Property 11: Soft delete preserves data
- [x] Implement Property 12: Updated tenant reflects changes on retrieval
- [x] Implement Property 13: API Key regeneration invalidates old key
- [x] All property tests pass with 100+ examples each

**Dependencies**: Task 1.1 (testing infrastructure)

**Estimated Effort**: 6-8 hours

**Actual Effort**: ~1.5 hours

**Files Created/Modified**:
- `tests/test_tenant_crud_properties.py` (new) - 500+ lines
- `TASK_1.2_COMPLETED.md` (documentation)

**Test Results**:
- 19 tests passing
- 92% code coverage
- All 8 correctness properties validated

**Correctness Properties Validated**:
- Property 6-13: Tenant CRUD operations ✅

---

### Task 1.3: Property-Based Tests for Azure Configuration

**Status**: `pending`

**Description**: Implement property-based tests for Azure DevOps configuration management.

**Acceptance Criteria**:
- [ ] Create `tests/test_azure_config_properties.py`
- [ ] Implement Property 14: Tenant with Azure config can retrieve it
- [ ] Implement Property 15: Azure config update reflects on retrieval
- [ ] Implement Property 16: Tenant without Azure config returns None
- [ ] Implement Property 17: Azure config validation (non-empty fields)
- [ ] All property tests pass with 100+ examples each

**Dependencies**: Task 1.1

**Estimated Effort**: 3-4 hours

**Files to Create/Modify**:
- `tests/test_azure_config_properties.py` (new)

**Correctness Properties Validated**:
- Property 14-17: Azure configuration

---

### Task 1.4: Property-Based Tests for Integrations

**Status**: `pending`

**Description**: Implement property-based tests for tenant integration management (Slack, Sheets, etc.).

**Acceptance Criteria**:
- [ ] Create `tests/test_integrations_properties.py`
- [ ] Implement Property 18: Enabled integration returns config
- [ ] Implement Property 19: Disabled integration returns None
- [ ] Implement Property 20: Integration type validation
- [ ] Implement Property 21: Integration config is valid JSON
- [ ] Implement Property 22: Multiple integrations per tenant supported
- [ ] All property tests pass with 100+ examples each

**Dependencies**: Task 1.1

**Estimated Effort**: 4-5 hours

**Files to Create/Modify**:
- `tests/test_integrations_properties.py` (new)

**Correctness Properties Validated**:
- Property 18-22: Integration management

---

### Task 1.5: Property-Based Tests for Tenant Settings

**Status**: `pending`

**Description**: Implement property-based tests for tenant settings management.

**Acceptance Criteria**:
- [ ] Create `tests/test_settings_properties.py`
- [ ] Implement Property 23: Default settings created with tenant
- [ ] Implement Property 24: Settings update reflects on retrieval
- [ ] Implement Property 25: Blocked authors/branches are valid JSON arrays
- [ ] Implement Property 26: Language and timezone validation
- [ ] All property tests pass with 100+ examples each

**Dependencies**: Task 1.1

**Estimated Effort**: 3-4 hours

**Files to Create/Modify**:
- `tests/test_settings_properties.py` (new)

**Correctness Properties Validated**:
- Property 23-26: Tenant settings

---

### Task 1.6: Integration Tests for Tenant API Endpoints

**Status**: `pending`

**Description**: Implement integration tests for all tenant management REST API endpoints.

**Acceptance Criteria**:
- [ ] Create `tests/test_tenant_api_integration.py`
- [ ] Test GET /api/tenants (list all tenants)
- [ ] Test POST /api/tenants (create tenant)
- [ ] Test GET /api/tenants/{id} (get tenant by ID)
- [ ] Test PUT /api/tenants/{id} (update tenant)
- [ ] Test DELETE /api/tenants/{id} (soft delete tenant)
- [ ] Test POST /api/tenants/{id}/regenerate-key (regenerate API Key)
- [ ] Test authentication with valid/invalid API Keys
- [ ] Test error responses (400, 401, 404, 409, 500)
- [ ] All integration tests pass

**Dependencies**: Task 1.1

**Estimated Effort**: 6-8 hours

**Files to Create/Modify**:
- `tests/test_tenant_api_integration.py` (new)

**Correctness Properties Validated**:
- Property 27-34: API endpoint behavior

---

### Task 1.7: Integration Tests for Tenant Middleware

**Status**: `pending`

**Description**: Implement integration tests for the tenant identification middleware.

**Acceptance Criteria**:
- [ ] Create `tests/test_tenant_middleware_integration.py`
- [ ] Test API Key extraction from Authorization header
- [ ] Test API Key extraction from X-API-Key header
- [ ] Test API Key extraction from query parameter
- [ ] Test fallback to default tenant when no API Key
- [ ] Test invalid API Key handling
- [ ] Test concurrent requests with different tenants
- [ ] Test cache behavior (hit/miss scenarios)
- [ ] All integration tests pass

**Dependencies**: Task 1.1

**Estimated Effort**: 5-6 hours

**Files to Create/Modify**:
- `tests/test_tenant_middleware_integration.py` (new)

**Correctness Properties Validated**:
- Property 2, 3, 4: Middleware behavior

---

### Task 1.8: End-to-End Tests for Admin Panel

**Status**: `pending`

**Description**: Implement end-to-end tests for the frontend administration panel using Selenium or Playwright.

**Acceptance Criteria**:
- [ ] Install Selenium or Playwright
- [ ] Create `tests/test_admin_panel_e2e.py`
- [ ] Test tenant list display
- [ ] Test tenant creation flow
- [ ] Test tenant edit flow
- [ ] Test tenant deletion flow
- [ ] Test API Key regeneration flow
- [ ] Test API Key configuration modal
- [ ] Test error handling in UI
- [ ] All E2E tests pass

**Dependencies**: Task 1.1

**Estimated Effort**: 8-10 hours

**Files to Create/Modify**:
- `tests/test_admin_panel_e2e.py` (new)
- `requirements.txt` (add selenium or playwright)

---

## Phase 2: Security Enhancements

### Task 2.1: Encrypt Sensitive Data at Rest

**Status**: `pending`

**Description**: Implement encryption for sensitive data (PAT tokens, Slack tokens) stored in the database.

**Acceptance Criteria**:
- [ ] Install `cryptography` library
- [ ] Create `integrations/encryption.py` module
- [ ] Implement `encrypt_value()` and `decrypt_value()` functions using Fernet
- [ ] Generate and store encryption key securely (environment variable)
- [ ] Modify `tenant_azure_config.pat_token` to store encrypted values
- [ ] Modify `tenant_integrations.config` to encrypt sensitive fields
- [ ] Create migration script to encrypt existing data
- [ ] Update `Tenant` class to decrypt values on access
- [ ] Add tests for encryption/decryption
- [ ] Document encryption key management in README

**Dependencies**: None

**Estimated Effort**: 6-8 hours

**Files to Create/Modify**:
- `integrations/encryption.py` (new)
- `integrations/tenant_context.py` (modify Tenant class)
- `migrations/002_encrypt_sensitive_data.py` (new)
- `README.md` (document encryption)

**Security Impact**: HIGH - Protects sensitive credentials

---

### Task 2.2: Implement Rate Limiting

**Status**: `pending`

**Description**: Add rate limiting to tenant management API endpoints to prevent abuse.

**Acceptance Criteria**:
- [ ] Install `flask-limiter` library
- [ ] Configure rate limiter in `app.py`
- [ ] Apply rate limits to tenant API endpoints:
  - List tenants: 100 requests/hour
  - Create tenant: 10 requests/hour
  - Update tenant: 50 requests/hour
  - Delete tenant: 10 requests/hour
  - Regenerate key: 5 requests/hour
- [ ] Return 429 Too Many Requests when limit exceeded
- [ ] Add rate limit headers to responses
- [ ] Test rate limiting behavior
- [ ] Document rate limits in API documentation

**Dependencies**: None

**Estimated Effort**: 3-4 hours

**Files to Create/Modify**:
- `app.py` (add rate limiting)
- `requirements.txt` (add flask-limiter)
- `INTERFAZ_ADMINISTRACION_TENANTS.md` (document rate limits)

**Security Impact**: MEDIUM - Prevents API abuse

---

### Task 2.3: Implement Audit Logging

**Status**: `pending`

**Description**: Add comprehensive audit logging for all tenant modifications.

**Acceptance Criteria**:
- [ ] Create `tenant_audit_log` table with fields: id, tenant_id, action, old_value, new_value, changed_by, changed_at, ip_address
- [ ] Create `integrations/audit.py` module
- [ ] Implement `log_tenant_change()` function
- [ ] Log all tenant create/update/delete operations
- [ ] Log API Key regeneration
- [ ] Log Azure config changes
- [ ] Log integration changes
- [ ] Create API endpoint GET /api/tenants/{id}/audit-log
- [ ] Add audit log display in admin panel
- [ ] Test audit logging

**Dependencies**: None

**Estimated Effort**: 5-6 hours

**Files to Create/Modify**:
- `migrations/003_create_audit_log.sql` (new)
- `integrations/audit.py` (new)
- `app.py` (add audit endpoint)
- `templates/index.html` (add audit log display)

**Security Impact**: HIGH - Provides accountability

---

### Task 2.4: Implement IP Allowlisting for Enterprise Tenants

**Status**: `pending`

**Description**: Add IP allowlisting feature for enterprise plan tenants.

**Acceptance Criteria**:
- [ ] Add `allowed_ips` field to `tenant_settings` table (JSON array)
- [ ] Create middleware to check IP allowlist
- [ ] Apply IP check only to enterprise tenants
- [ ] Return 403 Forbidden if IP not allowed
- [ ] Add IP allowlist configuration in admin panel
- [ ] Support CIDR notation for IP ranges
- [ ] Test IP allowlisting behavior
- [ ] Document IP allowlisting feature

**Dependencies**: None

**Estimated Effort**: 4-5 hours

**Files to Create/Modify**:
- `migrations/004_add_ip_allowlist.sql` (new)
- `app.py` (add IP check middleware)
- `templates/index.html` (add IP allowlist UI)

**Security Impact**: MEDIUM - Adds network-level security

---

## Phase 3: Performance Optimization

### Task 3.1: Implement LRU Cache with TTL

**Status**: `pending`

**Description**: Replace simple dictionary cache with LRU cache that has TTL (time-to-live) for tenant lookups.

**Acceptance Criteria**:
- [ ] Install `cachetools` library
- [ ] Replace `_tenant_cache` with `TTLCache` from cachetools
- [ ] Set cache max size to 1000 tenants
- [ ] Set TTL to 5 minutes
- [ ] Add cache hit/miss metrics
- [ ] Test cache eviction behavior
- [ ] Test TTL expiration
- [ ] Document cache configuration

**Dependencies**: None

**Estimated Effort**: 2-3 hours

**Files to Create/Modify**:
- `integrations/tenant_context.py` (modify cache implementation)
- `requirements.txt` (add cachetools)

**Performance Impact**: MEDIUM - Prevents unbounded cache growth

---

### Task 3.2: Implement Database Connection Pooling

**Status**: `pending`

**Description**: Add connection pooling for SQLite to improve concurrent request handling.

**Acceptance Criteria**:
- [ ] Install `sqlalchemy` library
- [ ] Create `integrations/database.py` module
- [ ] Configure SQLAlchemy connection pool
- [ ] Set pool size to 10 connections
- [ ] Set pool timeout to 30 seconds
- [ ] Migrate all database queries to use connection pool
- [ ] Test concurrent request performance
- [ ] Measure performance improvement
- [ ] Document database configuration

**Dependencies**: None

**Estimated Effort**: 6-8 hours

**Files to Create/Modify**:
- `integrations/database.py` (new)
- `integrations/state.py` (migrate to connection pool)
- `integrations/tenant_context.py` (use connection pool)
- `requirements.txt` (add sqlalchemy)

**Performance Impact**: HIGH - Improves concurrent request handling

---

### Task 3.3: Add Database Indexes

**Status**: `pending`

**Description**: Add database indexes to optimize common queries.

**Acceptance Criteria**:
- [ ] Create index on `tenants.api_key` (if not already exists)
- [ ] Create index on `tenants.subdomain`
- [ ] Create index on `tenants.status`
- [ ] Create index on `tenant_integrations(tenant_id, integration_type)`
- [ ] Create index on `tenant_audit_log.tenant_id`
- [ ] Create index on `tenant_audit_log.changed_at`
- [ ] Measure query performance before/after
- [ ] Document index strategy

**Dependencies**: Task 2.3 (audit log table)

**Estimated Effort**: 2-3 hours

**Files to Create/Modify**:
- `migrations/005_add_indexes.sql` (new)

**Performance Impact**: MEDIUM - Speeds up queries

---

### Task 3.4: Implement Query Result Caching

**Status**: `pending`

**Description**: Cache frequently accessed tenant data beyond just API Key lookups.

**Acceptance Criteria**:
- [ ] Cache tenant list queries (5 minute TTL)
- [ ] Cache tenant by ID queries (5 minute TTL)
- [ ] Cache Azure config queries (10 minute TTL)
- [ ] Cache integration queries (10 minute TTL)
- [ ] Invalidate cache on updates
- [ ] Add cache statistics endpoint
- [ ] Test cache behavior
- [ ] Document caching strategy

**Dependencies**: Task 3.1 (LRU cache)

**Estimated Effort**: 4-5 hours

**Files to Create/Modify**:
- `integrations/tenant_context.py` (add query caching)
- `app.py` (add cache stats endpoint)

**Performance Impact**: MEDIUM - Reduces database load

---

## Phase 4: Monitoring & Observability

### Task 4.1: Implement Structured Logging

**Status**: `pending`

**Description**: Replace print statements with structured logging using Python's logging module.

**Acceptance Criteria**:
- [ ] Configure logging in `app.py`
- [ ] Set log level from environment variable (default: INFO)
- [ ] Use JSON formatter for structured logs
- [ ] Add tenant_id to all log messages
- [ ] Add request_id to all log messages
- [ ] Log all tenant operations (create, update, delete)
- [ ] Log all authentication attempts
- [ ] Log all errors with stack traces
- [ ] Test logging output
- [ ] Document logging configuration

**Dependencies**: None

**Estimated Effort**: 4-5 hours

**Files to Create/Modify**:
- `app.py` (configure logging)
- `integrations/tenant_context.py` (add logging)
- `integrations/azure.py` (add logging)
- `integrations/slack.py` (add logging)

**Observability Impact**: HIGH - Enables debugging and monitoring

---

### Task 4.2: Add Prometheus Metrics

**Status**: `pending`

**Description**: Expose Prometheus metrics for monitoring tenant system health.

**Acceptance Criteria**:
- [ ] Install `prometheus-flask-exporter` library
- [ ] Configure Prometheus exporter in `app.py`
- [ ] Expose metrics endpoint at `/metrics`
- [ ] Add custom metrics:
  - `tenant_count` (gauge by status)
  - `tenant_api_requests_total` (counter by endpoint)
  - `tenant_cache_hits_total` (counter)
  - `tenant_cache_misses_total` (counter)
  - `tenant_operations_duration_seconds` (histogram)
- [ ] Test metrics collection
- [ ] Document metrics in README

**Dependencies**: None

**Estimated Effort**: 3-4 hours

**Files to Create/Modify**:
- `app.py` (add Prometheus exporter)
- `requirements.txt` (add prometheus-flask-exporter)
- `README.md` (document metrics)

**Observability Impact**: HIGH - Enables monitoring

---

### Task 4.3: Implement Health Check Endpoint

**Status**: `pending`

**Description**: Add health check endpoint for load balancers and monitoring systems.

**Acceptance Criteria**:
- [ ] Create GET /health endpoint
- [ ] Check database connectivity
- [ ] Check cache availability
- [ ] Check Azure DevOps connectivity (optional)
- [ ] Return 200 OK if healthy
- [ ] Return 503 Service Unavailable if unhealthy
- [ ] Include health details in response
- [ ] Test health check behavior
- [ ] Document health check endpoint

**Dependencies**: None

**Estimated Effort**: 2-3 hours

**Files to Create/Modify**:
- `app.py` (add health check endpoint)

**Observability Impact**: MEDIUM - Enables uptime monitoring

---

### Task 4.4: Add Request Tracing

**Status**: `pending`

**Description**: Implement distributed tracing for request flows across components.

**Acceptance Criteria**:
- [ ] Install `opentelemetry` libraries
- [ ] Configure OpenTelemetry in `app.py`
- [ ] Add trace context propagation
- [ ] Instrument tenant operations
- [ ] Instrument database queries
- [ ] Instrument external API calls
- [ ] Export traces to Jaeger or similar
- [ ] Test tracing behavior
- [ ] Document tracing setup

**Dependencies**: None

**Estimated Effort**: 6-8 hours

**Files to Create/Modify**:
- `app.py` (configure OpenTelemetry)
- `requirements.txt` (add opentelemetry packages)
- `README.md` (document tracing)

**Observability Impact**: HIGH - Enables performance debugging

---

## Phase 5: Documentation

### Task 5.1: Create User Guide

**Status**: `pending`

**Description**: Write comprehensive user guide for administrators using the tenant management system.

**Acceptance Criteria**:
- [ ] Create `docs/USER_GUIDE.md`
- [ ] Document how to access the admin panel
- [ ] Document how to configure API Key
- [ ] Document how to create a new tenant
- [ ] Document how to edit tenant configuration
- [ ] Document how to configure Azure DevOps
- [ ] Document how to configure integrations (Slack, Sheets)
- [ ] Document how to regenerate API Keys
- [ ] Document how to delete tenants
- [ ] Include screenshots of admin panel
- [ ] Include troubleshooting section

**Dependencies**: None

**Estimated Effort**: 4-5 hours

**Files to Create/Modify**:
- `docs/USER_GUIDE.md` (new)

---

### Task 5.2: Create API Documentation

**Status**: `pending`

**Description**: Write comprehensive API documentation for developers integrating with the tenant system.

**Acceptance Criteria**:
- [ ] Create `docs/API_REFERENCE.md`
- [ ] Document authentication (API Key)
- [ ] Document all tenant endpoints with examples
- [ ] Document request/response schemas
- [ ] Document error codes and messages
- [ ] Document rate limits
- [ ] Include curl examples for each endpoint
- [ ] Include Python client examples
- [ ] Include JavaScript client examples
- [ ] Document best practices

**Dependencies**: None

**Estimated Effort**: 5-6 hours

**Files to Create/Modify**:
- `docs/API_REFERENCE.md` (new)

---

### Task 5.3: Create Developer Guide

**Status**: `pending`

**Description**: Write developer guide for contributors to the tenant system codebase.

**Acceptance Criteria**:
- [ ] Create `docs/DEVELOPER_GUIDE.md`
- [ ] Document architecture overview
- [ ] Document code organization
- [ ] Document how to add new integration types
- [ ] Document how to extend tenant settings
- [ ] Document testing strategy
- [ ] Document database migrations
- [ ] Document deployment process
- [ ] Include contribution guidelines
- [ ] Include code style guide

**Dependencies**: None

**Estimated Effort**: 5-6 hours

**Files to Create/Modify**:
- `docs/DEVELOPER_GUIDE.md` (new)

---

### Task 5.4: Create Deployment Guide

**Status**: `pending`

**Description**: Write deployment guide for deploying the multi-tenant system to production.

**Acceptance Criteria**:
- [ ] Create `docs/DEPLOYMENT_GUIDE.md`
- [ ] Document environment variables
- [ ] Document database setup
- [ ] Document encryption key generation
- [ ] Document Azure DevOps setup
- [ ] Document Slack integration setup
- [ ] Document Google Sheets integration setup
- [ ] Document reverse proxy configuration (nginx)
- [ ] Document SSL/TLS setup
- [ ] Document backup strategy
- [ ] Document monitoring setup
- [ ] Include Docker deployment option
- [ ] Include Kubernetes deployment option

**Dependencies**: None

**Estimated Effort**: 6-8 hours

**Files to Create/Modify**:
- `docs/DEPLOYMENT_GUIDE.md` (new)
- `Dockerfile` (new, optional)
- `docker-compose.yml` (new, optional)
- `k8s/` (new directory, optional)

---

### Task 5.5: Update README

**Status**: `pending`

**Description**: Update main README with multi-tenant system information.

**Acceptance Criteria**:
- [ ] Add multi-tenant overview section
- [ ] Add quick start guide
- [ ] Add links to all documentation
- [ ] Add architecture diagram
- [ ] Add feature list
- [ ] Add requirements section
- [ ] Add installation instructions
- [ ] Add configuration instructions
- [ ] Add testing instructions
- [ ] Add contributing section
- [ ] Add license information

**Dependencies**: Tasks 5.1, 5.2, 5.3, 5.4

**Estimated Effort**: 3-4 hours

**Files to Create/Modify**:
- `README.md` (update)

---

## Phase 6: Migration & Cleanup

### Task 6.1: Create Migration Rollback Scripts

**Status**: `pending`

**Description**: Create rollback scripts for all database migrations to enable safe rollback if needed.

**Acceptance Criteria**:
- [ ] Create rollback script for multi-tenant schema migration
- [ ] Create rollback script for encryption migration
- [ ] Create rollback script for audit log migration
- [ ] Create rollback script for IP allowlist migration
- [ ] Create rollback script for indexes migration
- [ ] Test all rollback scripts
- [ ] Document rollback procedures

**Dependencies**: Tasks 2.1, 2.3, 2.4, 3.3

**Estimated Effort**: 3-4 hours

**Files to Create/Modify**:
- `migrations/rollback_001.sql` (new)
- `migrations/rollback_002.py` (new)
- `migrations/rollback_003.sql` (new)
- `migrations/rollback_004.sql` (new)
- `migrations/rollback_005.sql` (new)

---

### Task 6.2: Remove Legacy Code

**Status**: `pending`

**Description**: Remove or deprecate legacy code that is no longer needed after multi-tenant migration.

**Acceptance Criteria**:
- [ ] Identify legacy single-tenant code
- [ ] Mark deprecated functions with warnings
- [ ] Create deprecation timeline
- [ ] Update code to use new tenant-aware functions
- [ ] Remove hardcoded configuration values
- [ ] Test that all functionality still works
- [ ] Document breaking changes

**Dependencies**: All Phase 1 tasks (ensure tests pass)

**Estimated Effort**: 4-5 hours

**Files to Create/Modify**:
- Various files (remove legacy code)
- `CHANGELOG.md` (document breaking changes)

---

### Task 6.3: Create Data Migration Tools

**Status**: `pending`

**Description**: Create tools to help migrate existing single-tenant deployments to multi-tenant.

**Acceptance Criteria**:
- [ ] Create `tools/migrate_to_multitenant.py` script
- [ ] Script creates default tenant from existing config
- [ ] Script migrates existing data to tenant tables
- [ ] Script generates API Key for default tenant
- [ ] Script validates migration success
- [ ] Script creates backup before migration
- [ ] Test migration script on sample data
- [ ] Document migration process

**Dependencies**: None

**Estimated Effort**: 5-6 hours

**Files to Create/Modify**:
- `tools/migrate_to_multitenant.py` (new)
- `docs/MIGRATION_GUIDE.md` (new)

---

## Summary

### Total Tasks: 33

### By Phase:
- **Phase 1 (Testing)**: 8 tasks
- **Phase 2 (Security)**: 4 tasks
- **Phase 3 (Performance)**: 4 tasks
- **Phase 4 (Monitoring)**: 4 tasks
- **Phase 5 (Documentation)**: 5 tasks
- **Phase 6 (Migration)**: 3 tasks

### Total Estimated Effort: 150-190 hours

### Priority Recommendations:

**High Priority** (Complete First):
1. Task 1.1-1.7: Testing (critical for production readiness)
2. Task 2.1: Encrypt sensitive data (security critical)
3. Task 2.3: Audit logging (compliance and security)
4. Task 4.1: Structured logging (debugging and monitoring)
5. Task 5.1-5.2: User and API documentation (usability)

**Medium Priority** (Complete Second):
1. Task 2.2: Rate limiting (prevent abuse)
2. Task 3.1-3.3: Performance optimizations (scalability)
3. Task 4.2-4.3: Metrics and health checks (monitoring)
4. Task 5.3-5.4: Developer and deployment guides

**Low Priority** (Nice to Have):
1. Task 1.8: E2E tests (can be manual initially)
2. Task 2.4: IP allowlisting (enterprise feature)
3. Task 3.4: Query caching (optimization)
4. Task 4.4: Request tracing (advanced debugging)
5. Task 6.1-6.3: Migration tools (one-time need)

### Suggested Sprint Plan:

**Sprint 1 (2 weeks)**: Tasks 1.1-1.7 (Testing foundation)
**Sprint 2 (2 weeks)**: Tasks 2.1, 2.3, 4.1 (Security and logging)
**Sprint 3 (1 week)**: Tasks 5.1-5.2 (Documentation)
**Sprint 4 (1 week)**: Tasks 2.2, 3.1-3.3 (Performance and rate limiting)
**Sprint 5 (1 week)**: Tasks 4.2-4.3, 5.3-5.4 (Monitoring and docs)
**Sprint 6 (1 week)**: Remaining tasks and polish

---

## Notes

- All tasks assume the core multi-tenant functionality is already implemented and working
- Focus is on hardening, testing, and documenting the existing system
- Security and testing tasks should be prioritized for production readiness
- Performance optimizations can be done incrementally based on actual usage patterns
- Documentation is critical for adoption and maintenance
