# ADR 0001: Make the support-team console the primary prototype interface

Status: accepted by the user, 2026-11-24.

## Context

The prototype must make investigation, evidence, approvals, and verified outcomes easy
to understand and demonstrate. It needs customer intake without expanding into a
complete customer commerce portal.

## Decision

Use a support-team console as the main interface, with a small customer complaint form
alongside it. The console will present cases, evidence, proposals, reviewer decisions,
and outcome timelines. The customer experience provides intake, progress, and requested
additional information.

## Consequences

- Backend workflow and API correctness precede UI implementation.
- Customer, operator and reviewer permissions are explicit and enforced server-side.
- Reviewers see exact action details and evidence before approving a refund.
- The frontend framework, detailed screens, attachment scope and hosting remain proposed.
- The decision authorizes planning these interfaces; it does not resume application
  implementation before the architecture discussion.
