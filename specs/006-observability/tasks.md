# Tasks: Operational Observability

**Input**: Design documents from `/specs/006-observability/`

## Phase 1: Contract and Configuration

- [x] T001 Specify the bounded metrics and safe-error context contract.
- [x] T002 Add optional strong-token configuration with validation and tests.

## Phase 2: Runtime Observability

- [x] T003 Add typed metrics response schema and token-protected versioned
      endpoint; test disabled, denied, and successful access.
- [x] T004 Add safe route/method/status/exception-type context to unhandled
      server error logs without exposing exception messages.
- [x] T005 Pass optional local Compose configuration and document operations,
      privacy limits, process-local behavior, and deployment secret handling.

## Phase 3: Verification

- [x] T006 Run focused and full available backend/frontend/security
      validations; inspect the complete diff, dependencies, generated
      artifacts, and scope. Record local PostgreSQL permission and Docker CLI
      limitations for CI verification.
