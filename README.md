# Customer Support Resolution Agent

A planned support resolution product for an electronics retailer: investigate a case,
establish policy and transaction facts, propose a resolution, obtain human approval,
execute safely, and verify the outcome.

## Current status

Planning and architecture review. The agreed prototype uses synthetic data and mock
payment, shipping, and ticketing providers. The main interface is a support-team console,
with a small customer complaint form. Real client integrations and deployment follow
prototype validation.

The existing `app/`, `mock_services/`, and `pyproject.toml` files are an incomplete,
untested draft from an earlier implementation attempt. They are not a runnable backend
and are not included in the planning baseline commit. Review them against the blueprint
before adopting them in an implementation milestone.

## Planning documents

- [Original project plan](customer-support-resolution-agent-plan.md)
- [Product blueprint and acceptance scenarios](docs/product-blueprint.md)
- [Architecture proposal and database walkthrough](docs/architecture.md)
- [Milestone backlog and collaboration process](docs/backlog.md)
- [Confirmed interface decision](docs/decisions/0001-support-console.md)

The original plan is preserved. The blueprint records subsequent scope decisions and
explicit Stage 1 instructions. Architecture items marked proposed remain open for
discussion; writing them down does not establish approval.

Setup, migration, seed, API, and test commands will be added when the corresponding
implementation works and has been verified. No model provider key is needed to build
or test the deterministic Stage 1 workflow.
