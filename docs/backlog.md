# Delivery backlog and working agreement

## Collaboration

Before each meaningful milestone, explain what is being built, why it matters, how it
will work, alternatives/tradeoffs, and the evidence required to call it complete. Invite
the user's research and feedback. Execute routine details within agreed scope; discuss
material scope, architecture, or cost changes before adopting them.

After each milestone, provide a walkthrough, changed files, verification results,
limitations, and a practical demonstration the user can try. Distinguish planned,
implemented, tested locally, and verified in CI; never report one as another.

## Milestones

### M0: Product and architecture blueprint

- [x] Preserve the original project plan.
- [x] Record the support console and customer form decision.
- [x] Draft product scope and acceptance scenarios.
- [x] Draft component responsibilities and database safety design.
- [x] Discuss the architecture and agree on synthetic business rules.
- [ ] Resolve proposed technology and identity choices before their implementation.

Exit: shared understanding of scope, business rules, architecture, and acceptance gates.

### M1: Engineering foundation

- [ ] Review/adopt or replace the incomplete early code draft.
- [ ] Lock Python/tool versions and dependencies in a clean project.
- [ ] Add environment example, local PostgreSQL Compose and setup instructions.
- [ ] Establish CI for checks that exist and pass locally.
- [x] Agree on remote Git hosting and publish the repository when authorized.

Exit: a clean checkout can install dependencies and run the initial meaningful checks.

### M2: Deterministic business workflow (Stage 1)

- [ ] PostgreSQL schema/migrations for all required tables and supporting seed records.
- [ ] Tenant-scoped identity, ownership and reviewer authorization checks.
- [ ] Synthetic electronics catalog, customers, orders, payments, deliveries, returns,
      tickets and versioned policies.
- [ ] Configurable mock payment, shipping and ticketing contracts.
- [ ] Deterministic eligibility, amount calculation and reason codes.
- [ ] Ticket, investigation, proposal, decision, execution, inspection and manual
      reconciliation APIs; minimum safe approval and execution path included here.
- [ ] Durable refund reservation/idempotency and separate audit events.
- [ ] Logging, error handling and minimal Langfuse trace linking.
- [ ] Unit and PostgreSQL integration tests, including duplicate/concurrent execution
      and provider failures; migration checks in CI.

Exit: manually resolve a synthetic case via APIs, prove blocked requests cannot move
money, and recover an uncertain refund with no duplicate. No LLM, RAG, harness,
LangGraph, MCP, Shopify, or OpenTelemetry in this stage.

### M3: AI assistance (Stage 2)

- [ ] Agree on model evaluation cases before selecting the model.
- [ ] Versioned policy ingestion/retrieval with references and effective-date filtering.
- [ ] Typed tools with injected identity and service-enforced authorization.
- [ ] Small harness: allowlists, config, budgets, validation, safe retry limits.
- [ ] One agent baseline, LangGraph state/routing, persisted checkpoints.
- [ ] Evidence-backed proposals and agent/tool/retrieval observations in Langfuse.
- [ ] Add specialist agents only if evaluation supports them.

Exit: produce validated proposals with citations; financial enforcement remains deterministic.

### M4: Reliability and reviewer experience (Stage 3)

- [ ] Support-team console, case details, evidence panel and approval queue.
- [ ] Small customer form, progress view and additional-information flow.
- [ ] Durable worker execution, approval expiry, recovery and reconciliation sweep.
- [ ] Independent ticket-update retry, operational status and failure timelines.
- [ ] Restart, concurrency, stale approval and uncertain-result end-to-end tests.

Exit: demonstrate recovery and reviewer decisions without duplicate financial effects.

### M5: Complete prototype (Stage 4)

- [ ] Around 60 synthetic evaluation cases with held-out cases and expected outcomes.
- [ ] Repeatability checks and controlled live-model evaluations with usage limits.
- [ ] Simulation scenarios, useful metrics and budget/error visibility.
- [ ] Interface checks, end-to-end tests, container build and versioned artifacts.
- [ ] Reproducible documentation and demo of success, refusal and failure recovery.

Exit: another developer can reproduce the reported synthetic results from a clean checkout.

### M6: Client integration and deployment planning

- [ ] Validate merchant needs, data handling, pilot scope and operating budget.
- [ ] Select one real integration; begin read-only and shadow testing.
- [ ] Specify hosting, secret management, backup/restore, access controls and monitoring.
- [ ] Choose demo/staging deployment and then a controlled client rollout.

Exit: a concrete pilot plan based on measured prototype behavior and merchant requirements.

## Git and CI/CD

- Commit the planning baseline separately from untested application code.
- For each feature: acceptance criteria, focused branch, implementation/tests, reviewable
  commit, PR after remote setup, passing CI, review, merge.
- Keep `main` usable at the maturity claimed by its README; planning-only is a valid
  initial state, but not a working application.
- Do not publish a remote repository or choose its visibility without agreement.
- Keep secrets out of Git; use environment variables locally and managed CI secrets later.
- CI grows with actual functionality: lint/package checks, then unit/database/migration
  checks, then AI contracts and interface/end-to-end validation.
- Most automated tests use deterministic mocks. Schedule/manual-trigger live model
  evaluations separately with explicit provider and cost limits.
- CD initially means reproducible versioned artifacts. Automated deployment follows
  the hosting decision; do not create a pipeline that claims to deploy before a target exists.

## Initial feature sequence

After the architecture discussion: reproducible setup and CI; schema/migrations; seed
fixtures; authentication/ownership; tickets and reads; eligibility/proposals; reviewer
decisions; refund reservation/execution/reconciliation; audit/trace integration and
Stage 1 end-to-end validation. Add and run relevant tests throughout each feature.
