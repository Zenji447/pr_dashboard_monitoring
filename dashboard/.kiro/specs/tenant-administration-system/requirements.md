# Requirements Document: Tenant Administration System

## Introduction

The Tenant Administration System enables the PR Dashboard application to serve multiple organizations (tenants) with isolated configurations, integrations, and data. Each tenant operates independently with their own Azure DevOps configuration, integration settings, and API Key for secure access. The system provides administrative interfaces for managing the complete tenant lifecycle, from creation through configuration updates to deactivation.

## Glossary

- **Tenant**: An organization or client using the PR Dashboard application with isolated configuration and data
- **API_Key**: A unique cryptographic token that identifies and authenticates a tenant's requests
- **Tenant_Middleware**: Flask middleware component that identifies the tenant for each HTTP request
- **Tenant_Context**: Thread-safe storage mechanism that maintains the current tenant for request processing
- **Tenant_Cache**: In-memory cache that stores tenant lookups by API Key for performance
- **Admin_Panel**: Web-based user interface for managing tenant lifecycle and configuration
- **Soft_Delete**: Deactivation of a tenant by changing status to 'inactive' without removing data
- **Default_Tenant**: The fallback tenant (ID=1) used for backwards compatibility when no API Key is provided
- **Azure_Config**: Azure DevOps connection settings including organization URL, project, repository, and PAT token
- **Integration**: External service connection (Slack, Google Sheets, email, webhook) with tenant-specific configuration
- **Plan**: Subscription tier (basic, pro, enterprise) that determines tenant capabilities

## Requirements

### Requirement 1: Tenant Identification

**User Story:** As a system operator, I want every HTTP request to be associated with a specific tenant, so that the application can provide isolated configurations and data for each organization.

#### Acceptance Criteria

1. WHEN an HTTP request includes a valid API Key in the Authorization header, THEN THE Tenant_Middleware SHALL identify and set the corresponding tenant in the Tenant_Context
2. WHEN an HTTP request includes a valid API Key in the X-API-Key header, THEN THE Tenant_Middleware SHALL identify and set the corresponding tenant in the Tenant_Context
3. WHEN an HTTP request includes a valid API Key as a query parameter, THEN THE Tenant_Middleware SHALL identify and set the corresponding tenant in the Tenant_Context
4. WHEN an HTTP request includes an invalid API Key, THEN THE Tenant_Middleware SHALL log a warning and continue without setting a tenant
5. WHEN an HTTP request includes no API Key, THEN THE Tenant_Middleware SHALL set the Default_Tenant for backwards compatibility
6. WHEN the Tenant_Middleware looks up a tenant by API Key, THEN THE Tenant_Cache SHALL be checked before querying the database
7. WHEN a tenant is retrieved from the database, THEN THE Tenant_Cache SHALL store the result for subsequent requests

### Requirement 2: Tenant Context Management

**User Story:** As a developer, I want tenant information to be available throughout request processing, so that all components can access tenant-specific configuration without passing parameters.

#### Acceptance Criteria

1. WHEN a tenant is set in the Tenant_Context, THEN THE system SHALL make it accessible to all components during that request
2. WHEN multiple concurrent requests are processed, THEN THE Tenant_Context SHALL maintain isolation between requests using thread-safe storage
3. WHEN tenant configuration is accessed, THEN THE system SHALL lazy-load Azure_Config, integrations, and settings only when needed
4. WHEN a component requests the current tenant, THEN THE Tenant_Context SHALL return the tenant in less than 0.1ms
5. WHEN a tenant is retrieved from cache, THEN THE lookup SHALL complete in less than 1ms
6. WHEN a tenant is retrieved from the database, THEN THE lookup SHALL complete in less than 10ms

### Requirement 3: Tenant Creation

**User Story:** As an administrator, I want to create new tenants with their initial configuration, so that new organizations can start using the PR Dashboard application.

#### Acceptance Criteria

1. WHEN creating a tenant, THE Admin_Panel SHALL require subdomain, company_name, and plan fields
2. WHEN creating a tenant, THE system SHALL generate a unique API Key with format "prm_" followed by 43 random characters
3. WHEN creating a tenant, THE system SHALL validate that the subdomain is unique across all tenants
4. WHEN creating a tenant, THE system SHALL validate that the plan is one of: basic, pro, or enterprise
5. WHEN creating a tenant with Azure_Config, THE system SHALL create the tenant_azure_config record with org_url, project, and repository
6. WHEN creating a tenant with integrations, THE system SHALL create tenant_integrations records for each specified integration type
7. WHEN creating a tenant, THE system SHALL create a tenant_settings record with default values
8. WHEN a tenant is successfully created, THE system SHALL return the complete tenant object including the generated API Key
9. WHEN a tenant creation fails due to duplicate subdomain, THE system SHALL return a 409 Conflict error
10. WHEN a tenant is created, THE system SHALL set the status to 'active' by default

### Requirement 4: Tenant Retrieval

**User Story:** As an administrator, I want to view all tenants and their configurations, so that I can monitor and manage the organizations using the system.

#### Acceptance Criteria

1. WHEN listing tenants, THE system SHALL return all tenants with status 'active'
2. WHEN listing tenants, THE system SHALL include tenant id, subdomain, company_name, api_key, plan, status, and created_at
3. WHEN listing tenants, THE system SHALL include the complete Azure_Config for each tenant
4. WHEN listing tenants, THE system SHALL include the count of active integrations for each tenant
5. WHEN retrieving a tenant by API Key, THE system SHALL return the tenant if the API Key matches and status is 'active'
6. WHEN retrieving a tenant by API Key that doesn't exist, THE system SHALL return None
7. WHEN retrieving a tenant by ID, THE system SHALL return the tenant regardless of status

### Requirement 5: Tenant Updates

**User Story:** As an administrator, I want to update tenant configurations, so that I can modify settings as organizational needs change.

#### Acceptance Criteria

1. WHEN updating a tenant, THE system SHALL allow modification of company_name, plan, and status fields
2. WHEN updating a tenant, THE system SHALL allow modification of Azure_Config including org_url, project, repository, and pat_token
3. WHEN updating a tenant, THE system SHALL allow modification of integration configurations
4. WHEN updating a tenant, THE system SHALL validate that the plan is one of: basic, pro, or enterprise
5. WHEN updating a tenant, THE system SHALL validate that the status is one of: active or inactive
6. WHEN a tenant is updated, THE system SHALL clear the Tenant_Cache to ensure fresh data on subsequent requests
7. WHEN updating Azure_Config, THE system SHALL use INSERT OR REPLACE to handle both creation and updates
8. WHEN updating integrations, THE system SHALL use INSERT OR REPLACE to handle both creation and updates
9. WHEN a tenant update succeeds, THE system SHALL return the updated tenant object

### Requirement 6: Tenant Deletion

**User Story:** As an administrator, I want to deactivate tenants that are no longer using the system, so that I can prevent access while preserving data for audit purposes.

#### Acceptance Criteria

1. WHEN deleting a tenant, THE system SHALL perform a Soft_Delete by setting status to 'inactive'
2. WHEN deleting a tenant, THE system SHALL preserve all tenant data including configuration and settings
3. WHEN a tenant is deleted, THE system SHALL clear the Tenant_Cache to prevent access via cached data
4. WHEN a tenant with status 'inactive' is looked up by API Key, THE system SHALL not return the tenant
5. WHEN a tenant deletion succeeds, THE system SHALL return a success response

### Requirement 7: API Key Management

**User Story:** As an administrator, I want to regenerate tenant API Keys, so that I can maintain security if a key is compromised or needs rotation.

#### Acceptance Criteria

1. WHEN regenerating an API Key, THE system SHALL generate a new unique API Key with format "prm_" followed by 43 random characters
2. WHEN regenerating an API Key, THE system SHALL update the tenant record with the new API Key
3. WHEN an API Key is regenerated, THE system SHALL clear the Tenant_Cache to invalidate the old key
4. WHEN an API Key is regenerated, THE system SHALL return the new API Key to the administrator
5. WHEN the old API Key is used after regeneration, THE system SHALL not identify a valid tenant

### Requirement 8: Endpoint Protection

**User Story:** As a security engineer, I want tenant management endpoints to require authentication, so that only authorized users can manage tenant configurations.

#### Acceptance Criteria

1. WHEN a request to a protected endpoint includes no API Key, THE system SHALL return a 401 Unauthorized error
2. WHEN a request to a protected endpoint includes an invalid API Key, THE system SHALL return a 401 Unauthorized error
3. WHEN a request to a protected endpoint includes a valid tenant API Key, THE system SHALL process the request
4. WHEN a request to a legacy endpoint requires the global API_KEY, THE system SHALL validate against the configured API_KEY environment variable
5. WHEN the global API_KEY is not configured, THE system SHALL return a 503 Service Unavailable error

### Requirement 9: Frontend Administration Interface

**User Story:** As an administrator, I want a web-based interface to manage tenants, so that I can perform administrative tasks without using API clients or command-line tools.

#### Acceptance Criteria

1. WHEN the Admin_Panel loads, THE system SHALL display a table of all active tenants
2. WHEN the Admin_Panel displays tenants, THE system SHALL show subdomain, company name, plan, status, API Key (truncated), and active integrations count
3. WHEN the Admin_Panel loads, THE system SHALL display KPIs including total tenants, active tenants, enterprise tenants, and total active integrations
4. WHEN an administrator clicks "Crear Tenant", THE Admin_Panel SHALL open a modal with a form for tenant creation
5. WHEN an administrator submits the create form, THE Admin_Panel SHALL send a POST request to create the tenant
6. WHEN a tenant is successfully created, THE Admin_Panel SHALL display the generated API Key in a modal
7. WHEN an administrator clicks "Editar" on a tenant, THE Admin_Panel SHALL open a modal pre-filled with the tenant's current configuration
8. WHEN an administrator submits the edit form, THE Admin_Panel SHALL send a PUT request to update the tenant
9. WHEN an administrator clicks "Eliminar" on a tenant, THE Admin_Panel SHALL request confirmation before deleting
10. WHEN an administrator confirms deletion, THE Admin_Panel SHALL send a DELETE request to deactivate the tenant
11. WHEN an administrator clicks "Regenerar Key", THE Admin_Panel SHALL request confirmation before regenerating
12. WHEN an administrator confirms key regeneration, THE Admin_Panel SHALL display the new API Key
13. WHEN an administrator clicks "Recargar", THE Admin_Panel SHALL refresh the tenant list from the server

### Requirement 10: Data Validation

**User Story:** As a system operator, I want tenant data to be validated before storage, so that the system maintains data integrity and prevents invalid configurations.

#### Acceptance Criteria

1. WHEN validating a subdomain, THE system SHALL ensure it contains only lowercase letters, numbers, and hyphens
2. WHEN validating a subdomain, THE system SHALL ensure it is unique across all tenants
3. WHEN validating a company_name, THE system SHALL ensure it is a non-empty string
4. WHEN validating a plan, THE system SHALL ensure it is one of: basic, pro, or enterprise
5. WHEN validating a status, THE system SHALL ensure it is one of: active or inactive
6. WHEN validating an API Key, THE system SHALL ensure it starts with "prm_" and has 43 total characters
7. WHEN validating Azure_Config, THE system SHALL ensure org_url, project, and repository are non-empty strings
8. WHEN validating an integration_type, THE system SHALL ensure it is one of: slack, sheets, email, or webhook
9. WHEN validating integration config, THE system SHALL ensure it is valid JSON

### Requirement 11: Error Handling

**User Story:** As a developer, I want the system to handle errors gracefully, so that failures are logged, reported appropriately, and don't crash the application.

#### Acceptance Criteria

1. WHEN a database operation fails, THE system SHALL log the error with full stack trace
2. WHEN a database transaction fails, THE system SHALL rollback the transaction
3. WHEN a database error occurs, THE system SHALL return a 500 Internal Server Error response
4. WHEN an invalid API Key is provided, THE system SHALL log a warning with the truncated API Key
5. WHEN a duplicate subdomain is detected, THE system SHALL return a 409 Conflict error with message "El subdominio ya existe"
6. WHEN a tenant has invalid integration configuration, THE system SHALL log a warning and return None for that integration
7. WHEN an integration function encounters invalid configuration, THE system SHALL handle gracefully by skipping the operation

### Requirement 12: Performance Optimization

**User Story:** As a system operator, I want the tenant identification system to be performant, so that it doesn't add significant latency to request processing.

#### Acceptance Criteria

1. WHEN a tenant is looked up by API Key and exists in cache, THE lookup SHALL complete in less than 1ms
2. WHEN a tenant is looked up by API Key and not in cache, THE lookup SHALL complete in less than 10ms
3. WHEN the current tenant is retrieved from context, THE operation SHALL complete in less than 0.1ms
4. WHEN a tenant is retrieved from the database, THE system SHALL store it in the Tenant_Cache
5. WHEN tenant configuration is accessed, THE system SHALL lazy-load the configuration only when first accessed
6. WHEN the Tenant_Cache is cleared, THE system SHALL remove all cached tenant entries

### Requirement 13: Security

**User Story:** As a security engineer, I want tenant API Keys to be cryptographically secure, so that they cannot be easily guessed or brute-forced.

#### Acceptance Criteria

1. WHEN generating an API Key, THE system SHALL use cryptographically secure random generation
2. WHEN generating an API Key, THE system SHALL produce 256 bits of entropy
3. WHEN generating an API Key, THE system SHALL ensure uniqueness across all tenants
4. WHEN an API Key is displayed after creation, THE system SHALL show it only once
5. WHEN an API Key is displayed in the tenant list, THE system SHALL show only a truncated version
6. WHEN a tenant is deleted via Soft_Delete, THE system SHALL preserve all data for audit purposes

### Requirement 14: Integration Configuration

**User Story:** As an administrator, I want to configure external service integrations per tenant, so that each organization can use their own Slack workspace, Google Sheets, and other services.

#### Acceptance Criteria

1. WHEN a tenant has a Slack integration, THE system SHALL store the Slack token in the integration config
2. WHEN a tenant has a Google Sheets integration, THE system SHALL store the sheet ID in the integration config
3. WHEN a tenant has an email integration, THE system SHALL store the email configuration in the integration config
4. WHEN a tenant has a webhook integration, THE system SHALL store the webhook URL in the integration config
5. WHEN checking if a tenant has an integration, THE system SHALL verify the integration exists and is enabled
6. WHEN retrieving an integration, THE system SHALL return the integration config if enabled
7. WHEN retrieving an integration that is disabled, THE system SHALL return None

### Requirement 15: Tenant Settings

**User Story:** As an administrator, I want to configure tenant-specific settings, so that each organization can customize their experience with language, timezone, and filtering preferences.

#### Acceptance Criteria

1. WHEN a tenant is created, THE system SHALL initialize settings with default language 'es'
2. WHEN a tenant is created, THE system SHALL initialize settings with default timezone 'America/Mexico_City'
3. WHEN a tenant is created, THE system SHALL initialize settings with empty blocked_authors list
4. WHEN a tenant is created, THE system SHALL initialize settings with empty blocked_branches list
5. WHEN tenant settings are accessed, THE system SHALL parse blocked_authors as a JSON array
6. WHEN tenant settings are accessed, THE system SHALL parse blocked_branches as a JSON array
7. WHEN tenant settings include a logo_url, THE system SHALL make it available for branding
8. WHEN tenant settings include a primary_color, THE system SHALL make it available for theming
