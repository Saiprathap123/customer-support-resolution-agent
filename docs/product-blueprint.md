# Prototype product blueprint

Status: working planning baseline, 2026-11-24.

## Purpose and intended user

Build a working prototype with market potential, then plan real client integrations
and deployment. The initial retailer sells electronics. The product helps its support
team reach verified resolutions using business evidence, policy references, controlled
actions, and human review.

The main experience is a support-team console. A small customer complaint form provides
intake, case progress, and requests for additional information. The operator investigates
and manages cases; an authenticated reviewer approves or rejects refund proposals.
The same demonstration user may hold both staff permissions, but permissions are
enforced explicitly. A customer's order identifier alone establishes no access.

## Prototype scope

The complete prototype covers the core engine in the original plan's Stages 1-4:

- Order-status complaints using current shipment records.
- Returned-item refunds with deterministic eligibility and amount calculation.
- Damaged-item complaints with required evidence collection and human escalation when
  an allowed resolution cannot be established. Image interpretation and automatic
  replacement ordering are not assumed features.
- Customer authentication, ownership checks, and role-based staff authorization.
- Versioned policy records, later retrieval and citations.
- Human approval bound to an exact, persisted action proposal.
- Stable refund idempotency, balance reservation, verification, and reconciliation.
- Separate audit events and operational observability.
- A reviewer interface, simulation cases, evaluation, documentation, and automated checks.

Boundaries: one fictional store, one currency, synthetic data, mock external providers,
one issue per workflow, and all refunds require human approval. Exclude chargebacks,
fraud adjudication, complex partial returns, voice, WhatsApp, Shopify, MCP, and live
merchant onboarding. No independent reusable agent platform is a prototype deliverable.

## Accepted synthetic refund rules

Accepted by the user on 2026-11-24; see [ADR 0002](decisions/0002-synthetic-refund-policy.md).

- INR; full-order returns and refunds only. No split payments, fees, partial quantities,
  or automatic exceptions in the initial execution path.
- One fully captured payment matching the order's paid amount and currency.
- Return requested within 30 days after confirmed delivery, then received and inspection passed.
- Refund the full paid amount. Existing refunds or reservations prevent another full refund.
- Maximum executable refund: INR 10,000 (1000000 minor units). Larger cases escalate;
  this does not establish that the customer is financially ineligible.
- Every refund requires approval, valid for 24 hours. Material proposal or evidence
  changes require a fresh proposal and approval.
- Select the applicable synthetic policy version by delivery date; evaluate the return
  request against that version's window.
- Damaged-item complaints require evidence collection and human review, not an automatic
  refund based solely on the complaint.

## Open design details

- Staff permissions: specify what operators can inspect or execute and whether reviewers
  may approve proposals they created. Do not assume segregation-of-duties rules silently.
- Evidence requirements for damaged items: define the prototype input and storage scope.

The early application draft must be aligned with these rules before adoption.

## Representative resolution

Customer: "I returned my headphones last week, but my refund has not arrived."

1. Authenticate the customer and check order ownership.
2. Create a ticket and a persisted workflow run.
3. Read order, payment, delivery, return, and existing refund facts.
4. Determine the applicable policy and missing evidence.
5. Produce an answer, clarification, escalation, or refund proposal.
6. Calculate any refund in deterministic code and request human approval.
7. Authenticate the reviewer and record the decision against the exact proposal.
8. Revalidate the approved action and reserve the refundable balance.
9. Commit the reservation before calling the provider with a stable key.
10. Verify the result; reconcile uncertainty before claiming success or issuing another action.
11. Persist the outcome and independently synchronize the support ticket.

In Stage 1 these steps are exercised manually through APIs. Stage 2 adds model-assisted
investigation, retrieval, and proposals. Authorization and financial enforcement stay in
application services regardless of how a workflow is initiated.

## Acceptance scenarios

| ID | Scenario | Required observable outcome |
| --- | --- | --- |
| A01 | Customer asks for shipment status | Response matches the latest mock shipping record |
| A02 | Eligible refund receives valid approval | Exactly one confirmed provider refund and matching application accounting |
| A03 | Return is ineligible | Stable reason code; no provider refund |
| A04 | Customer supplies someone else's order or tenant resource | Access denied without leaking resource details |
| A05 | Reviewer rejects or approval expires | Execution blocked and decision/expiry visible |
| A06 | Material proposal or evidence changes | Old approval cannot authorize a changed action |
| A07 | Concurrent execution or repeated request | No duplicate refund and no overspent balance |
| A08 | Provider accepts refund, then response is lost | Funds remain reserved; reconciliation finds the existing refund |
| A09 | Application restarts with an uncertain operation | Persisted operation and stable key support recovery |
| A10 | Refund succeeds but ticket update fails | Refund remains successful; retry affects only ticket synchronization |
| A11 | Damaged-item evidence is insufficient | Targeted clarification or human escalation; no invented eligibility |
| A12 | AI recommends an action | Typed proposal includes supporting records and applicable policy citations |
| A13 | Agent exceeds a budget or requests a forbidden tool | Agent stops or escalates; financial controls remain effective |

Financial assertions inspect both the application database and provider records. Model
judgments and convincing customer language do not prove that money moved correctly.

## Product evidence

Measure workflow correctness, confirmed resolution, unauthorized actions, duplicate
refunds, review effort, active latency, reviewer wait, and model cost when applicable.
Report denominators and distinguish synthetic results from real merchant performance.
Claims of customer demand and business value remain hypotheses until validated.
