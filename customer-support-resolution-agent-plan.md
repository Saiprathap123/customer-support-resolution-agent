# Build a Customer Support Resolution Agent (v2)

**Stack:** Python, LangGraph, FastAPI, PostgreSQL, Langfuse, OpenTelemetry

**What you'll build:** A support system that investigates customer problems, retrieves relevant policies, proposes solutions, executes approved actions, verifies the outcome, and records everything.

> **What changed in v2:** two additions to the original plan.
> 1. **A thin Agent Harness** around the agents (Section 6): tool permissions, budgets, validation, retries, prompt versions, record/replay, evaluation hooks.
> 2. **Langfuse + OpenTelemetry observability** (Section 16): traces, cost, latency, and tool-call errors for every run, kept separate from the audit trail.
>
> The core workflow is unchanged. An appendix at the end lists the product layer to add after the core engine works.

---

## 1. The project in one sentence

Build an AI agent that takes a customer complaint from **"What happened?"** to **"Here's the verified outcome"**, using business data, support policies, APIs, and human approval.

A typical interaction:

> **Customer:** "I returned my headphones last week, but I still haven't received my refund."

Your system should:

1. Identify the authenticated customer.
2. Retrieve the order, return, and payment records.
3. Find the applicable refund policy.
4. Determine whether a refund is eligible, already processing, or blocked.
5. Propose an appropriate action.
6. Request human approval before issuing a new refund.
7. Call the refund API after approval and validation.
8. Update the support ticket.
9. Explain what happened without claiming more than the API confirmed.

**Use synthetic customer data and a mock payment service throughout the initial project.**

---

## 2. Positioning and relevance

Do not position this as "AI customer support." That market is crowded. Position it around **verified resolution**: investigate, validate policy, propose action, execute safely, confirm the actual outcome.

It also demonstrates the skills Forward Deployed Engineering roles look for:

| Skill | How the project demonstrates it |
| --- | --- |
| Understanding business requirements | Translate support policies into workflows and eligibility rules |
| Integrating systems | Connect customer, order, payment, and ticket APIs |
| Building AI workflows | Combine retrieval, reasoning, tool calls, and structured outputs |
| Managing risk | Authorization, approval, transaction controls, budgets |
| Handling messy conditions | Recover from missing information, timeouts, and duplicate requests |
| Operating AI in production | Tracing, cost tracking, tool-error monitoring, consistency testing |
| Measuring business value | Verified resolution, escalation, latency, cost per ticket |
| Communicating tradeoffs | Explain why some steps use an LLM and others use ordinary code |

**The strongest story is how reliably the system handles a customer problem, including when it should stop and ask for help.**

---

## 3. Define a manageable first version

Build for a fictional online electronics retailer. Support three complaint types:

- **A. Order status:** retrieve the order and shipment status, explain the latest available information, update the ticket.
- **B. Refund request:** check eligibility, prepare a proposal, obtain approval, execute, verify.
- **C. Damaged item:** retrieve the order and policy, collect required information, prepare a resolution or escalate.

For the first version:

- One store and one currency.
- Human approval for every refund.
- Mock shipping, payment, and ticketing services.
- One customer issue per workflow.
- Customer messaging stays inside your demo interface.
- Exclude chargebacks, fraud adjudication, complex partial returns, voice, WhatsApp, and multiple ecommerce platforms.

Write these boundaries in your README.

---

## 4. Design the workflow before choosing agents

```
Customer submits complaint
          ↓
Authenticate and validate request
          ↓
Classify complaint
          ↓
Retrieve customer/order facts + relevant policies
          ↓
Check for missing information
          ↓
Create proposed resolution
          ↓
Validate against business rules
          ↓
   ┌──────┼──────────────┐
   ↓      ↓              ↓
Answer  Request       Escalate
only    approval      to human
          ↓
Approve / reject / expire
          ↓
Revalidate approved action
          ↓
Execute tool call
          ↓
Verify external result
          ↓
Update ticket and audit trail
          ↓
Return accurate customer update
```

**Important distinction:** the model proposes actions. Your application decides whether those actions are permitted and executes them through controlled services. Every box above emits a trace span (Section 16).

---

## 5. Choose an architecture

Six components:

### FastAPI application
Customer requests, authentication and authorization, workflow creation, status queries, reviewer decisions, input and response validation.

### LangGraph workflow
The workflow engine: classification, investigation, policy retrieval, proposals, approval pauses, execution, verification, escalation.

### Agent harness (new)
A thin layer of your own code around every agent call. It enforces tool permissions, step, time, and cost budgets, output validation, retries, and prompt versioning. Details in Section 6.

### PostgreSQL
Customers, orders, tickets, workflow runs, policy metadata and chunks, approvals, refund operations, audit events, and durable workflow checkpoints. Keep application tables and LangGraph checkpoint tables logically separate.

### Mock external services
Payment/refund, shipping, and ticketing APIs. Make them capable of returning errors, delays, and duplicate responses so you can test realistic failures.

### Observability stack (new)
Langfuse for LLM-specific traces, cost, latency, and evaluation scores; OpenTelemetry for application-level traces. Details in Section 16.

**Optional:** pgvector for policy embeddings inside PostgreSQL.

---

## 6. The agent harness (new)

LangGraph is the workflow engine. The harness is a small layer of your own code around the agents. It is not a replacement for LangGraph and not a general-purpose framework. Build only what LangGraph does not give you.

### What the harness controls

```
Agent Harness
├── Agent configuration
├── Prompt/version management
├── Model selection and gateway
├── Tool registry and permissions
├── Tool-call validation
├── Step limits
├── Timeout limits
├── Token/cost budgets
├── Retry policies
├── Structured output validation
├── Human approval policy hooks
├── Trace context
├── Record and replay
└── Evaluation hooks
```

### Example configuration

```python
ResolutionAgent(
    model="<configured-model-id>",
    prompt_version="resolution_v3",
    allowed_tools=[
        "get_order",
        "search_policy",
        "create_refund_proposal",
    ],
    max_steps=8,
    timeout_seconds=30,
    max_cost_usd=0.10,
    require_structured_output=True,
    output_schema=ResolutionProposal,
    retry_policy=RetryPolicy(model_calls=2, read_tools=2, write_tools=0),
)
```

This is much stronger than a bare `agent.invoke(...)`: every agent has an explicit contract.

### Responsibilities and rules

| Concern | Rule |
| --- | --- |
| **Tool registry** | Each agent sees only its allowed tools. The registry enforces this at call time, not just in the prompt. The investigation agent never receives a write tool. |
| **Tool-call validation** | Arguments are validated against typed schemas before the call runs. Unknown tools and malformed arguments are rejected and logged. |
| **Identity injection** | The harness injects tenant, customer, and reviewer identity from the authenticated context. These fields never appear in the schema the model can fill. |
| **Budgets** | Max steps, tool calls, tokens, cost, and wall-clock time per run. Checked before every step. On exhaustion the run stops and escalates with the evidence gathered so far. |
| **Retries** | Bounded exponential backoff for model calls and read tools. **Never retry a write tool blindly**; write retries go through the idempotent execution path in Section 13. |
| **Structured output** | Validate against the schema. Allow one limited repair attempt, then stop or escalate. |
| **Model gateway** | One place for timeouts, retries, fallback model, and cost logging. You can use LiteLLM here instead of writing your own. |
| **Prompt versioning** | Prompts live in version-controlled files. Each run records the prompt version (content hash) and model ID. |
| **Approval policy** | The harness flags actions that require approval. **Enforcement stays in the execution service**, which checks the stored approval. A flag alone authorizes nothing. |
| **Trace context** | Every model call, tool call, and retrieval runs inside a span tagged with run and tenant context. |
| **Record and replay** | Optionally record tool inputs and outputs so a run can be replayed without calling external services. |
| **Evaluation hooks** | After a run, the harness emits scores (schema valid, budget used, tool errors) to Langfuse and the eval harness. |

### The harness is not a security boundary

Authorization, ownership checks, refund amounts, eligibility, and approval validity are enforced in the services and database, never only in the harness or the prompt. The harness reduces mistakes; the services prevent harm.

### Run modes

```
run once          normal production behavior
replay            re-run a recorded case with recorded tool responses
repeat N          run the same case N times
compare           compare trajectories, tool calls, evidence, and final decisions
detect drift      flag changes between prompt, model, or code versions
```

The repeat and compare modes power the consistency tests in Section 17. Over time the harness becomes reusable infrastructure for your other agent projects.

### Build order

Start with the tool registry, config object, and budget checks. Add output validation and retries next. Add record/replay and evaluation hooks once the main workflow runs. Do not generalize it until a second agent needs the same behavior.

---

## 7. Implement a small multi-agent workflow

Start with one tool-using agent and deterministic control flow. Once it works, introduce specialists:

| Agent | Responsibility | Output |
| --- | --- | --- |
| Investigation agent | Gather customer, order, return, and payment facts | Structured evidence summary |
| Policy agent | Retrieve applicable policy passages | Citations and policy interpretation |
| Resolution agent | Combine facts and policy into a proposed action | Structured resolution proposal |

Each specialist is a harness-configured agent with its own tool allowlist and budget.

Use ordinary code for authentication, access control, amount calculations, eligibility enforcement, approval validation, API execution, retry limits, and state transitions.

If investigation and policy retrieval are independent, run them concurrently. If policy selection depends on the product or order date, gather those facts first.

**Portfolio experiment:** compare the specialist design against a single-agent baseline. Measure whether the extra coordination improves correctness enough to justify its cost and latency. Do not add multi-agent complexity unless evaluation shows it helps.

---

## 8. Design the database

| Table | Important fields |
| --- | --- |
| `customers` | `id`, `external_auth_subject`, `name`, `email` |
| `orders` | `id`, `customer_id`, `status`, `currency`, `paid_amount_minor`, `delivered_at` |
| `order_items` | `id`, `order_id`, `product_id`, `quantity`, `paid_amount_minor` |
| `returns` | `id`, `order_id`, `status`, `received_at`, `inspection_status` |
| `tickets` | `id`, `customer_id`, `order_id`, `category`, `status`, `summary` |
| `workflow_runs` | `id`, `ticket_id`, `thread_id`, `status`, `started_at`, `completed_at`, **`langfuse_trace_id`**, **`config_snapshot`** (agent configs, prompt versions, model IDs), **`budget_usage`** |
| `policy_documents` | `id`, `version`, `effective_from`, `effective_to`, `source_uri` |
| `policy_chunks` | `id`, `document_id`, `content`, `embedding`, `metadata` |
| `action_proposals` | `id`, `run_id`, `action_type`, `payload`, `payload_hash`, `status` |
| `approvals` | `id`, `proposal_id`, `reviewer_id`, `decision`, `expires_at`, `decided_at` |
| `refund_operations` | `id`, `order_id`, `proposal_id`, `amount_minor`, `idempotency_key`, `provider_reference`, `status` |
| `audit_events` | `id`, `run_id`, `actor`, `event_type`, `redacted_payload`, `created_at` |

If you plan to sell this later, add a `tenant_id` column to every table now. It is cheap today and painful to retrofit.

### Database rules worth implementing

- Store money in integer minor units (cents or paise).
- Unique constraint on each refund operation's idempotency key.
- Track successful refunds and amounts reserved by pending operations.
- Prevent total committed refunds from exceeding the refundable balance.
- Record approval timestamps and the exact proposal approved.
- Use migrations so another developer can reproduce the schema.

**A workflow checkpoint is not your financial ledger.** Keep refund accounting in application tables with explicit constraints and transactions.

---

## 9. Build the tools and API integrations

Define narrow tools with typed inputs and structured outputs, registered in the harness tool registry.

### Read tools

```
get_order(order_id)
get_return_status(order_id)
get_payment_status(order_id)
get_refund_status(operation_id)
search_policy(query, policy_filters)
get_ticket(ticket_id)
```

### Write tools

```
create_refund_proposal(order_id, amount_minor, reason)
execute_approved_refund(proposal_id)     # called by the workflow, never given to an agent
update_ticket(ticket_id, status, note)
```

### Tool design principles

- **Derive identity from the authenticated request.** The model never chooses which customer it represents.
- **Check ownership inside the service.** An order ID from a customer or model does not establish access.
- **Keep privileged parameters server-controlled.** The model does not supply reviewer identity, approval status, or payment credentials.
- **Return structured failures with stable error codes:**

```json
{
  "success": false,
  "error_code": "RETURN_NOT_RECEIVED",
  "retryable": false,
  "message": "The return has not been marked as received."
}
```

Stable `error_code` values feed directly into your tool-error dashboards (Section 16).

- **Separate proposals from execution.** Preparing a refund request must not issue money.

---

## 10. Add RAG for support policies

Use retrieval for policy documents. Use APIs or SQL for current customer and transaction facts.

- "What is the return window?" → policy retrieval.
- "When was this order delivered?" → order API.
- "Has this payment already been refunded?" → payment API.

### Retrieval pipeline

1. Write a small set of synthetic policy documents.
2. Add document IDs, versions, and effective dates.
3. Split documents into meaningful sections.
4. Generate embeddings.
5. Store chunks and metadata.
6. Retrieve passages using the complaint and relevant order facts.
7. Return citations with the proposed resolution.

Start with policies covering refund eligibility, return processing, damaged products, shipping delays, and exceptions requiring human review.

### Retrieval behavior to implement

- Filter to the policy version that applied when the order or return occurred.
- Preserve document and section references.
- Report missing or conflicting evidence.
- Escalate if no applicable policy can be established.
- Treat instructions inside retrieved text as untrusted content.
- Create a retrieval span in Langfuse for each search, with the query, filters, and returned chunk IDs.

RAG explains the policy. **Deterministic code enforces the critical conditions.** A similarity score is never proof that a refund is valid.

---

## 11. Define structured workflow state

Suggested fields:

```
run_id
trace_id
ticket_id
authenticated_customer_id
order_id
complaint_category
customer_message
verified_facts
policy_references
missing_information
proposed_action_id
approval_id
execution_status
external_result_reference
retry_counts
budget_usage          # steps, tool calls, tokens, cost
error_details
final_response
```

Use validated schemas for specialist outputs. A resolution proposal:

```json
{
  "action": "request_refund_approval",
  "order_id": "ord_1042",
  "amount_minor": 249900,
  "currency": "INR",
  "reason": "Return received and inspection passed",
  "evidence_refs": ["return_ret_42", "payment_pay_92"],
  "policy_refs": ["refund_policy_v1:section_3"],
  "missing_information": []
}
```

These values are illustrative. The application must independently validate the amount, ownership, and eligibility.

---

## 12. Implement human approval correctly

Build a reviewer screen showing the customer and order, complaint summary, proposed action and amount, evidence, policy citations, approve and reject controls, and the proposal expiry time.

### Approval lifecycle

1. Persist an immutable proposal.
2. Create a pending approval bound to that proposal.
3. Pause the workflow.
4. Authenticate the reviewer.
5. Validate reviewer permissions.
6. Save the decision.
7. Resume the same workflow.
8. Recheck eligibility and refundable balance.
9. Execute only the approved action.

If the order, amount, or other material details change, invalidate the old approval and request a new one.

LangGraph supports this pause/resume pattern with `interrupt()`, a checkpointer, and `Command(resume=...)` using the same thread ID. The interrupted node restarts when resumed, so code before the interrupt may run again. Keep financial side effects in a separate execution step.

**An approval message in chat is not authorization.** The execution service verifies the stored approval and the authenticated reviewer decision.

---

## 13. Make refunds safe to retry

A difficult but valuable test case:

> The payment service accepts the refund, but your application times out before receiving the response.

Blindly retrying with a new request can create a duplicate refund.

### Suggested execution pattern

1. Create a durable refund operation with a stable idempotency key.
2. In a short database transaction, validate the approval and reserve the refundable amount.
3. Commit before calling the external service.
4. Call the provider with the stable key.
5. Persist its response.
6. If the result is uncertain, mark the operation `unknown` or `pending_reconciliation`.
7. Query the provider by key or reference before deciding what to do next.
8. Retry with the same key only when the provider's contract supports it.

Your mock payment API should implement this contract: repeated requests with the same key and payload return the same operation; a changed payload is rejected.

For concurrent requests, use `SELECT ... FOR UPDATE` or equivalent transactional controls when checking and reserving balances, and avoid holding that transaction open during a network call.

A checkpoint alone does not guarantee that an external action happens exactly once.

---

## 14. Expose the workflow through FastAPI

| Endpoint | Purpose |
| --- | --- |
| `POST /tickets` | Create a customer support ticket |
| `POST /tickets/{ticket_id}/runs` | Start a resolution workflow |
| `GET /runs/{run_id}` | Retrieve status and output |
| `GET /runs/{run_id}/events` | Retrieve a redacted event timeline |
| `GET /approvals` | List approvals available to the reviewer |
| `POST /approvals/{approval_id}/decision` | Approve or reject a proposal |
| `POST /runs/{run_id}/messages` | Supply additional customer information |
| `GET /health` | Check application health |

Check authorization on every endpoint. Add OpenTelemetry instrumentation to FastAPI so each request links to its workflow trace.

### Execution approach

For the earliest prototype, run short workflows directly and return when they finish or pause.

For a more robust version: persist a job, return `202 Accepted` with a run ID, execute through a worker, persist progress, and let clients query status. A worker is also needed for approval expiry and a periodic reconciliation sweep of uncertain refunds. FastAPI `BackgroundTasks` is fine for small in-process work but is not enough once real money is in flight.

---

## 15. Handle failures explicitly

| Failure | Expected behavior |
| --- | --- |
| Missing order information | Ask a targeted clarification question |
| Order belongs to another customer | Deny access without revealing details |
| No applicable policy found | Escalate rather than invent eligibility |
| Conflicting policy evidence | Flag the conflict for review |
| Temporary read API failure | Retry with bounded backoff |
| Invalid model output | Validate, one repair attempt, then stop or escalate |
| **Agent requests a tool it is not allowed to use** | **Reject, log, count as a harness violation, continue or escalate** |
| **Step, time, or cost budget exceeded** | **Stop the agent, escalate with evidence gathered, record in trace** |
| **Model provider timeout or outage** | **Retry, then fallback model, then escalate** |
| Approval rejected | Record the decision and follow the rejection path |
| Approval expired | Require a new valid approval |
| Refund outcome uncertain | Reconcile before retrying or claiming success |
| Refund succeeds, ticket update fails | Retry only the ticket update |
| Worker crashes | Resume from persisted state and reconcile side effects |
| Excessive workflow loops | Stop at a configured step or cost limit |

Customer-facing language must match the actual state:

> "Your refund request is awaiting approval."

> "The payment service accepted your refund request. Processing is still pending."

> "I couldn't confirm the refund outcome yet. The case is being checked."

Keep `submitted`, `processing`, `succeeded`, and `failed` distinct.

---

## 16. Observability and tracing with Langfuse and OpenTelemetry (new)

Do not build your own tracing platform.

### Tool roles

| Signal | Tool |
| --- | --- |
| LLM traces: prompts, responses, model, tokens, cost, latency, tool calls, retrieval spans, evaluation scores | **Langfuse** |
| Application traces: FastAPI requests, database queries, outbound HTTP to mock or real services | **OpenTelemetry** (check Langfuse's current docs for OpenTelemetry ingestion) |
| Logs, metrics, alarms | CloudWatch on AWS, or Prometheus and Grafana |
| Exceptions | Sentry |
| **Audit trail** | **Your own `audit_events` table in PostgreSQL, not Langfuse** |

### Example trace

```
Support Resolution Run #1842
│
├── classify_issue                 320 ms
│
├── investigation_agent           1.8 s
│   ├── get_order                 120 ms
│   ├── get_return_status          95 ms
│   └── get_payment_status        140 ms
│
├── policy_agent                  1.2 s
│   └── search_policy             180 ms
│
├── resolution_agent             1.5 s
│
├── approval_wait                18 min
│
├── execute_refund               430 ms
│
└── verify_refund                130 ms

LLM cost: $0.018
LLM calls: 4
Tool calls: 7
Errors: 0
Active latency: 5.7 sec
```

The numbers are illustrative. Report your own measured values.

### Conventions

- **One trace per workflow run**, with a span for each graph node, agent, tool call, and retrieval.
- **Tag every trace** with `run_id`, `ticket_id`, `prompt_version`, model ID, and (later) `tenant_id`. That gives per-ticket and per-tenant cost.
- **Use the run ID as the Langfuse session ID**, so the segments before and after an approval pause appear together. Do not leave one span open for the whole approval wait; measure approval wait from `approval_requested` and `approval_decided` audit timestamps instead.
- **Record tool failures** as span status plus your stable `error_code`, so you can chart failures by code (`RETURN_NOT_RECEIVED`, provider timeouts, and so on).
- **Store `langfuse_trace_id` on `workflow_runs`** so a ticket links to its trace.
- **Measure active execution time separately from reviewer wait time.**

### Keep observability and audit separate

| | Observability (Langfuse) | Audit trail (`audit_events`) |
| --- | --- | --- |
| Purpose | Debug, optimize, measure | Prove what happened |
| Retention | Can be sampled or expire | Retained per policy |
| Mutability | Tooling can prune | Append-only |
| Content | Rich, detailed | Redacted, minimal |

### Privacy and setup

- **Redact PII** (names, emails, addresses) before sending data to Langfuse by default.
- **Use your own Langfuse project** (cloud free tier or self-hosted). Do not use any employer's instance or data.
- Keep Langfuse keys in environment variables or a secrets manager.

### Dashboards and alerts to build

- Cost per ticket and per run.
- LLM calls and tool calls per run.
- p50 and p95 active latency.
- Tool error rate by `error_code`.
- Budget-exceeded and harness-violation counts.
- Schema-repair rate (a rising rate often means a prompt or model regression).
- Escalation rate and approval wait time.

---

## 17. Evaluate verified outcomes

Build an evaluation harness that seeds a scenario, runs the workflow (through the agent harness), supplies any simulated reviewer decision, and checks the resulting system state. This same harness becomes the merchant-facing simulation mode later.

Create around **60 synthetic cases**:

| Category | Suggested cases |
| --- | --- |
| Order status and shipment questions | 10 |
| Eligible refund requests | 10 |
| Ineligible refund requests | 10 |
| Missing information and ambiguous complaints | 10 |
| API failures, retries, and crashes | 10 |
| Authorization, concurrency, and adversarial inputs | 10 |

Keep a held-out subset you do not use while tuning prompts. Store the dataset in Langfuse datasets and run experiments there, so each prompt or model change has a comparable score.

### Store an expected outcome for each case

Relevant customer and order, applicable policy, allowed actions, forbidden actions, whether approval is required, expected final business state, and expected escalation or clarification behavior.

### Track these metrics

- **Verified resolution rate:** cases whose expected business outcome is confirmed, divided by cases designated resolvable.
- **Overall workflow correctness:** cases handled as expected (including correct clarification, refusal, and escalation), divided by all cases.
- **Unauthorized action count.**
- **Duplicate refund count** under retries, restarts, and concurrency.
- **Policy retrieval quality:** whether the required evidence appears in the retrieved results.
- **Grounded response quality:** whether factual claims are supported by records and tool results.
- **Operational metrics** (from Langfuse): latency, model calls, tool calls, retries, and cost per case.
- **Harness metrics:** budget-exceeded rate, tool-permission violations, schema-repair rate.

Use database assertions and mock-provider records for transactional outcomes. An LLM judge can help with response quality but must not decide whether money moved correctly. Report human-assisted and fully automated resolution separately.

### Consistency testing (new)

Use the harness `repeat N` and `compare` modes on a subset of cases (for example 20 runs each):

- Same classification?
- Same retrieved policy references?
- Same proposed action and amount?
- Same final business state?
- Same trajectory (tool-call sequence)?

Deterministic code should be 100% consistent by design. Measure variance on the LLM-driven parts: classification, evidence selection, and proposals. Set a target such as "same verdict on at least 90% of runs," and gate CI on drift between versions.

---

## 18. Build it in stages

### Stage 1: Business workflow, backend, observability foundation

Build:

- Synthetic policies and customer records.
- PostgreSQL schema and migrations.
- Customer authentication.
- Ticket endpoints.
- Mock order, shipping, and payment APIs (with duplicate, timeout, and error behavior).
- Deterministic refund eligibility checks.
- Langfuse project setup and OpenTelemetry on FastAPI.

**Done when:** you can manually resolve a sample ticket through the APIs without an LLM, and see the request in a trace.

### Stage 2: Harness, agents, and retrieval

Build:

- Harness skeleton: tool registry, agent config, budgets, output validation.
- Policy ingestion and retrieval.
- Typed tools.
- Complaint classification.
- Investigation and proposal generation.
- LangGraph state and routing.
- Langfuse spans for every agent, tool, and retrieval.

**Done when:** the system gathers evidence and produces a validated proposal with citations, and you can open the trace and see cost and latency per step.

### Stage 3: Approval and reliability

Build:

- Reviewer interface.
- Durable approval pause/resume.
- Idempotent refund operations.
- Retry and reconciliation behavior (including the worker and sweep).
- Ticket updates and audit trail.
- Failure handling for budgets, tool violations, and provider outages.

**Done when:** restarting or retrying a run does not issue duplicate refunds, and every failure type in Section 15 has a test.

### Stage 4: Evaluation and presentation

Build:

- Evaluation dataset in Langfuse and the eval runner.
- Baseline comparisons (single agent vs specialists).
- Consistency runs with the harness repeat mode.
- Cost, latency, and tool-error dashboards.
- Failure-case tests.
- Simple demo interface.
- README, architecture diagram, and demo recording.

**Done when:** another developer can run the project and reproduce your reported results.

---

## 19. Organize the repository

```
customer-support-resolution-agent/
├── app/
│   ├── main.py
│   ├── api/
│   ├── auth/
│   ├── schemas/
│   ├── agents/
│   ├── harness/              # tool registry, budgets, validation, retries, replay
│   ├── workflows/
│   ├── tools/
│   ├── services/
│   ├── policies/
│   ├── observability/        # Langfuse + OpenTelemetry setup, redaction, trace helpers
│   ├── prompts/              # versioned prompt files
│   └── db/
├── mock_services/
│   ├── payments/
│   └── shipping/
├── migrations/
├── scripts/
│   ├── seed_data.py
│   └── ingest_policies.py
├── evals/
│   ├── datasets/
│   ├── run_evals.py
│   ├── run_consistency.py
│   └── reports/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── failure_scenarios/
├── docs/
│   └── decisions/
├── docker-compose.yml
├── .env.example
├── pyproject.toml
└── README.md
```

Pin dependencies in a lockfile. Document model configuration, embedding configuration, required environment variables, and setup commands.

---

## 20. Create a demo that proves the system works

Show three scenarios, each with its Langfuse trace:

- **Demo A: Successful approved refund.** The customer submits a complaint, the agent retrieves records and policy, the reviewer approves, the mock provider records the refund, and the ticket receives the verified status.
- **Demo B: Correctly blocked request.** The customer requests an ineligible refund, the system explains the policy, no payment action occurs, and the case is escalated if appropriate.
- **Demo C: Failure recovery.** The provider accepts a refund but the response times out, the application restarts, the workflow reconciles the existing operation, and no second refund is created.

Add a short fourth clip: a run hitting its **cost budget**, stopping, and escalating with the evidence gathered.

The interface needs a complaint panel, workflow timeline, evidence and policy panel, approval queue, and final outcome panel. Display structured events and concise explanations, not private model reasoning.

---

## 21. Write a strong README and résumé entry

The README should cover:

1. The customer problem and supported scope.
2. Architecture and workflow.
3. The agent harness: what it enforces and what it deliberately leaves to the services.
4. Setup and seed-data instructions.
5. Tool contracts and approval design.
6. Refund idempotency and recovery behavior.
7. Observability: trace example, cost per ticket, error dashboards.
8. Evaluation methodology, consistency results, and measured numbers.
9. Known limitations.
10. Demo link.

**Résumé template (replace placeholders only after measuring):**

> Built a customer support resolution system using Python, LangGraph, FastAPI, and PostgreSQL, with a custom agent harness (tool permissions, budgets, validation, replay), Langfuse tracing, policy retrieval, human-approved refunds, and auditable ticket updates.

> Achieved [X%] verified resolution on [N] held-out synthetic cases at $[Y] average cost per ticket; tested duplicate-refund prevention and recovery across [M] retry, concurrency, and crash scenarios; measured [Z%] decision consistency over repeated runs.

Do not describe synthetic test results as production performance.

---

## 22. Final project checklist

- [ ] Customer access is derived from authenticated identity.
- [ ] Order ownership is checked server-side.
- [ ] Policies have versions and citations.
- [ ] Model outputs use validated schemas.
- [ ] Financial eligibility is enforced in code.
- [ ] Refunds require approval bound to an exact proposal.
- [ ] Expired or changed proposals require fresh approval.
- [ ] Retries and concurrent requests cannot duplicate refunds.
- [ ] Unknown payment outcomes trigger reconciliation.
- [ ] Ticket updates reflect verified external status.
- [ ] Workflow state survives a restart.
- [ ] Each agent has an explicit tool allowlist enforced by the harness.
- [ ] Execution tools are never exposed to an agent.
- [ ] Step, time, and cost budgets are enforced and tested.
- [ ] Prompt version and model ID are recorded for every run.
- [ ] Every run has a Langfuse trace linked from `workflow_runs`.
- [ ] Traces are tagged with run and (later) tenant IDs, and PII is redacted.
- [ ] The audit trail lives in PostgreSQL, separate from observability data.
- [ ] Tool errors are tracked by stable error code.
- [ ] Evaluation checks business state, not just response text.
- [ ] Consistency is measured over repeated runs.
- [ ] Results distinguish automated and human-assisted resolution.
- [ ] The README documents scope, tradeoffs, and limitations.

---

## Appendix: after the core engine works

The core engine above (Stages 1 to 4) is Phase 1. To turn it into a product, add the following in order. Do not start Phase 2 until you have talked to real merchants.

**Gate: talk to five Shopify merchants.** Ask about ticket volume, how they handle refunds today, which helpdesk they use, and what they would pay. Proceed only if at least two are interested in a pilot.

### Phase 2: Pilot build

- **Shopify, read-only first** (orders, fulfillment, refund status), then refund execution after approval and reconciliation are tested. Read Shopify's current refund and protected-customer-data requirements early, and make the mock behave like the real service.
- **One inbound channel** (email or one helpdesk) and **one identity check** (order number plus email, or a one-time code).
- **Tenant-aware schema:** `tenant_id` everywhere, per-merchant settings and encrypted credentials. Defer isolation hardening and self-serve onboarding.
- **Merchant approval queue** with evidence, policy citations, and outcome. Policies uploaded and versioned through an admin script or page you operate yourself.
- **Webhook handling** with signature verification and idempotent processing.
- **Per-tenant cost metering** from Langfuse tags, rate limits, and a **kill switch** that disables the agent instantly.
- **Deployment:** Docker, Terraform, AWS, secrets management, backups, staging environment, and CI with an eval gate.
- **Optional MCP layer** exposing read tools (and at most proposal creation). Never expose execution through MCP, and keep identity server-side.

### Phase 3: Shadow pilot

- Run in **shadow mode**: the agent proposes actions while the merchant's team handles tickets as usual, and you compare outcomes.
- Add monitoring alerts and short runbooks (refund error spike, queue backlog).
- Expose the **simulation environment** so merchants can test scenarios before enabling real actions.
- Move to live approvals for refunds only after the shadow results hold up.

### Ground rules

- Keep this repository separate from any employer's code, prompts, data, and accounts.
- Check your employment contract for exclusivity, conflict-of-interest, and IP clauses before taking a merchant.
- Do not use real shopper data without a written agreement. Check data protection obligations (India's DPDP Act, and GDPR for EU customers) with a professional.
- Keep refunds human-approved until measured results justify more automation.
