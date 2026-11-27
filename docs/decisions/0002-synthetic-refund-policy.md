# ADR 0002: Define the prototype's synthetic refund policy

Status: accepted by the user, 2026-11-24.

## Context

Deterministic eligibility and tests need explicit business rules. These rules describe
the fictional retailer's prototype policy, not statutory rights or a real merchant's policy.

## Decision

- Currency: INR; amounts stored as integer paise.
- Full-order returns and refunds only, excluding split payments, fees and partial quantities.
- Require confirmed delivery and one fully captured payment matching the order amount
  and currency.
- Return must be requested within 30 days of delivery, received and pass inspection.
- Select the policy version effective at delivery. Preserve its ID/version with evidence.
- Refund the entire paid order amount; earlier refunds and reserved amounts must not
  permit a second full refund.
- Execution cap: INR 10,000, inclusive (1000000 paise). Larger cases escalate to manual
  handling; exceeding the cap alone is not a finding of customer ineligibility.
- Every refund requires authenticated human approval bound to the exact stored proposal.
- Approval lifetime: 24 hours. Revalidate expiry and eligibility at execution time.
- Material changes to the proposal or supporting evidence require fresh approval.
- Damaged-item claims collect evidence and go to human review; a complaint alone cannot
  establish refund eligibility.

## Consequences

Enforcement belongs in business services and database accounting, never model prompts.
Persist a stable refund idempotency key, reserve funds transactionally, commit before
external calls, and retain reservations while outcomes are uncertain.

Tests must cover return-window boundaries, amounts at/above the cap, expired approvals,
changed evidence, existing refunds/reservations, ownership, and concurrent execution.
Specify exact timestamp boundary semantics in the eligibility feature before implementation.

Staff role details and damaged-item evidence storage remain open design work. Changes
to this accepted policy need an explicit discussion and a versioned decision.
