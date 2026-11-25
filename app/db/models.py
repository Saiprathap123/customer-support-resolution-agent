"""Tenant-scoped business records. Financial decisions remain in application services."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class TenantRecord:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (UniqueConstraint("tenant_id", "id"),)


def tenant_key(column: str, table: str) -> ForeignKeyConstraint:
    """All references include tenant identity; a bare object ID never establishes scope."""
    return ForeignKeyConstraint(["tenant_id", column], [f"{table}.tenant_id", f"{table}.id"])


def status_type(kind: type[StrEnum], name: str) -> Enum:
    # Text-backed checks avoid PostgreSQL enum-type migration overhead.
    return Enum(
        kind,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [item.value for item in members],
    )


class OrderStatus(StrEnum):
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    CAPTURED = "captured"
    FAILED = "failed"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"


class ReturnStatus(StrEnum):
    REQUESTED = "requested"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    REJECTED = "rejected"


class InspectionStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class TicketCategory(StrEnum):
    ORDER_STATUS = "order_status"
    REFUND = "refund"
    DAMAGED_ITEM = "damaged_item"


class TicketStatus(StrEnum):
    OPEN = "open"
    AWAITING_INFORMATION = "awaiting_information"
    AWAITING_APPROVAL = "awaiting_approval"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class RunStatus(StrEnum):
    STARTED = "started"
    AWAITING_INFORMATION = "awaiting_information"
    AWAITING_APPROVAL = "awaiting_approval"
    PROCESSING = "processing"
    PENDING_RECONCILIATION = "pending_reconciliation"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    FAILED = "failed"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    EXECUTED = "executed"


class ApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RefundStatus(StrEnum):
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING_RECONCILIATION = "pending_reconciliation"


class SyncStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Customer(TenantRecord, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "external_auth_subject"),
    )
    external_auth_subject: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))


class Product(TenantRecord, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "sku"),
    )
    sku: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))


class Order(TenantRecord, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "id", "customer_id"),
        tenant_key("customer_id", "customers"),
        CheckConstraint("paid_amount_minor > 0", name="positive_paid_amount"),
        CheckConstraint("refunded_amount_minor >= 0", name="nonnegative_refunded_amount"),
        CheckConstraint("reserved_amount_minor >= 0", name="nonnegative_reserved_amount"),
        CheckConstraint(
            "reserved_amount_minor <= paid_amount_minor - refunded_amount_minor",
            name="refund_balance_limit",
        ),
        CheckConstraint("currency = 'INR'", name="supported_currency"),
        CheckConstraint(
            "status != 'delivered' OR delivered_at IS NOT NULL",
            name="delivery_evidence",
        ),
        Index("ix_orders_tenant_customer", "tenant_id", "customer_id"),
    )
    customer_id: Mapped[UUID]
    status: Mapped[OrderStatus] = mapped_column(status_type(OrderStatus, "order_status"))
    currency: Mapped[str] = mapped_column(String(3))
    paid_amount_minor: Mapped[int] = mapped_column(BigInteger)
    refunded_amount_minor: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    reserved_amount_minor: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(TenantRecord, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_key("order_id", "orders"),
        tenant_key("product_id", "products"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("paid_amount_minor > 0", name="positive_paid_amount"),
        Index("ix_order_items_tenant_order", "tenant_id", "order_id"),
        Index("ix_order_items_tenant_product", "tenant_id", "product_id"),
    )
    order_id: Mapped[UUID]
    product_id: Mapped[UUID]
    quantity: Mapped[int] = mapped_column(Integer)
    paid_amount_minor: Mapped[int] = mapped_column(BigInteger)  # line total, not unit price


class Payment(TenantRecord, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "order_id"),
        UniqueConstraint("tenant_id", "provider_reference"),
        tenant_key("order_id", "orders"),
        CheckConstraint("amount_minor > 0", name="positive_amount"),
        CheckConstraint("currency = 'INR'", name="supported_currency"),
    )
    order_id: Mapped[UUID]
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[PaymentStatus] = mapped_column(status_type(PaymentStatus, "payment_status"))
    provider_reference: Mapped[str] = mapped_column(String(100))


class Delivery(TenantRecord, Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "order_id"),
        tenant_key("order_id", "orders"),
        CheckConstraint(
            "status != 'delivered' OR delivered_at IS NOT NULL",
            name="delivery_evidence",
        ),
    )
    order_id: Mapped[UUID]
    status: Mapped[DeliveryStatus] = mapped_column(status_type(DeliveryStatus, "delivery_status"))
    tracking_reference: Mapped[str] = mapped_column(String(100))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Return(TenantRecord, Base):
    __tablename__ = "returns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "order_id"),
        tenant_key("order_id", "orders"),
        CheckConstraint("received_at IS NULL OR received_at >= requested_at", name="receipt_order"),
        CheckConstraint("status != 'received' OR received_at IS NOT NULL", name="receipt_evidence"),
        CheckConstraint(
            "inspection_status = 'pending' OR received_at IS NOT NULL",
            name="inspection_evidence",
        ),
    )
    order_id: Mapped[UUID]
    status: Mapped[ReturnStatus] = mapped_column(status_type(ReturnStatus, "return_status"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inspection_status: Mapped[InspectionStatus] = mapped_column(
        status_type(InspectionStatus, "inspection_status"),
        server_default="pending",
    )


class Ticket(TenantRecord, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "id", "order_id"),
        tenant_key("customer_id", "customers"),
        ForeignKeyConstraint(
            ["tenant_id", "order_id", "customer_id"],
            ["orders.tenant_id", "orders.id", "orders.customer_id"],
        ),
        Index("ix_tickets_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_tickets_tenant_order", "tenant_id", "order_id"),
        Index("ix_tickets_tenant_status", "tenant_id", "status"),
    )
    customer_id: Mapped[UUID]
    order_id: Mapped[UUID]
    category: Mapped[TicketCategory] = mapped_column(status_type(TicketCategory, "ticket_category"))
    status: Mapped[TicketStatus] = mapped_column(
        status_type(TicketStatus, "ticket_status"),
        server_default="open",
    )
    summary: Mapped[str] = mapped_column(Text)
    provider_sync_status: Mapped[SyncStatus] = mapped_column(
        status_type(SyncStatus, "ticket_sync_status"),
        server_default="pending",
    )


class WorkflowRun(TenantRecord, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "id", "order_id"),
        UniqueConstraint("tenant_id", "thread_id"),
        ForeignKeyConstraint(
            ["tenant_id", "ticket_id", "order_id"],
            ["tickets.tenant_id", "tickets.id", "tickets.order_id"],
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="completion_order",
        ),
        CheckConstraint(
            "langfuse_trace_id IS NULL OR langfuse_trace_id ~ '^[0-9a-f]{32}$'",
            name="trace_id_format",
        ),
        Index("ix_workflow_runs_tenant_ticket", "tenant_id", "ticket_id"),
        Index("ix_workflow_runs_tenant_status", "tenant_id", "status"),
    )
    ticket_id: Mapped[UUID]
    order_id: Mapped[UUID]  # binds proposals to the ticket's order through composite keys
    thread_id: Mapped[UUID] = mapped_column(default=uuid4)
    status: Mapped[RunStatus] = mapped_column(
        status_type(RunStatus, "run_status"),
        server_default="started",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(32))
    config_snapshot: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    budget_usage: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    output: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class PolicyDocument(TenantRecord, Base):
    __tablename__ = "policy_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "name", "version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="effective_period",
        ),
        Index("ix_policy_documents_tenant_effective", "tenant_id", "name", "effective_from"),
    )
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(30))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_uri: Mapped[str] = mapped_column(String(500))


class PolicyChunk(TenantRecord, Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_key("document_id", "policy_documents"),
        UniqueConstraint("tenant_id", "document_id", "section_reference"),
    )
    document_id: Mapped[UUID]
    section_reference: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB)  # no retrieval/vector index yet
    chunk_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
    )


class ActionProposal(TenantRecord, Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "run_id"),
        UniqueConstraint("tenant_id", "id", "payload_hash"),
        UniqueConstraint("tenant_id", "id", "order_id", "amount_minor", "currency"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id", "order_id"],
            ["workflow_runs.tenant_id", "workflow_runs.id", "workflow_runs.order_id"],
        ),
        tenant_key("policy_document_id", "policy_documents"),
        CheckConstraint("action_type = 'refund'", name="supported_action"),
        CheckConstraint("amount_minor > 0", name="positive_amount"),
        CheckConstraint("currency = 'INR'", name="supported_currency"),
        CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="payload_hash_format"),
        Index("ix_action_proposals_tenant_order", "tenant_id", "order_id"),
        Index("ix_action_proposals_tenant_policy", "tenant_id", "policy_document_id"),
    )
    run_id: Mapped[UUID]
    order_id: Mapped[UUID]
    action_type: Mapped[str] = mapped_column(String(30), server_default="refund")
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    policy_document_id: Mapped[UUID]
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[ProposalStatus] = mapped_column(
        status_type(ProposalStatus, "proposal_status"),
        server_default="pending",
    )


class Approval(TenantRecord, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "proposal_id"),
        ForeignKeyConstraint(
            ["tenant_id", "proposal_id", "payload_hash"],
            ["action_proposals.tenant_id", "action_proposals.id", "action_proposals.payload_hash"],
        ),
        CheckConstraint("expires_at > created_at", name="expiry_order"),
        CheckConstraint(
            "(decision = 'pending' AND reviewer_id IS NULL AND decided_at IS NULL) OR "
            "(decision IN ('approved', 'rejected') AND reviewer_id IS NOT NULL "
            "AND decided_at IS NOT NULL AND decided_at >= created_at AND decided_at < expires_at)",
            name="decision_evidence",
        ),
        Index("ix_approvals_tenant_queue", "tenant_id", "decision", "expires_at"),
    )
    proposal_id: Mapped[UUID]
    payload_hash: Mapped[str] = mapped_column(String(64))
    reviewer_id: Mapped[str | None] = mapped_column(String(200))
    decision: Mapped[ApprovalDecision] = mapped_column(
        status_type(ApprovalDecision, "approval_decision"),
        server_default="pending",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefundOperation(TenantRecord, Base):
    __tablename__ = "refund_operations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "proposal_id"),
        UniqueConstraint("idempotency_key"),
        UniqueConstraint("tenant_id", "provider_reference"),
        tenant_key("order_id", "orders"),
        ForeignKeyConstraint(
            ["tenant_id", "proposal_id", "order_id", "amount_minor", "currency"],
            [
                "action_proposals.tenant_id",
                "action_proposals.id",
                "action_proposals.order_id",
                "action_proposals.amount_minor",
                "action_proposals.currency",
            ],
        ),
        CheckConstraint("amount_minor > 0", name="positive_amount"),
        CheckConstraint("currency = 'INR'", name="supported_currency"),
        CheckConstraint("length(idempotency_key) > 0", name="nonempty_idempotency_key"),
        CheckConstraint(
            "status != 'succeeded' OR provider_reference IS NOT NULL",
            name="success_evidence",
        ),
        Index("ix_refund_operations_tenant_order", "tenant_id", "order_id"),
        Index("ix_refund_operations_reconciliation", "tenant_id", "status", "created_at"),
    )
    order_id: Mapped[UUID]
    proposal_id: Mapped[UUID]
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[RefundStatus] = mapped_column(
        status_type(RefundStatus, "refund_status"),
        server_default="submitted",
    )
    error_code: Mapped[str | None] = mapped_column(String(60))


class AuditEvent(TenantRecord, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        tenant_key("run_id", "workflow_runs"),
        Index("ix_audit_events_tenant_run_created", "tenant_id", "run_id", "created_at"),
    )
    run_id: Mapped[UUID]
    actor: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(80))
    redacted_payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
