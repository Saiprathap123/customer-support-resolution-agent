from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import BigInteger, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Approval, AuditEvent, Customer, Order, RefundOperation, Ticket
from tests.integration.helpers import migration_config

pytestmark = pytest.mark.postgres


def test_migration_round_trip_and_no_metadata_drift(schema_factory) -> None:
    with schema_factory() as engine:
        with engine.begin() as connection:
            config = migration_config(connection)
            command.upgrade(config, "head")
            tables = set(inspect(connection).get_table_names())
            assert tables == {
                "alembic_version",
                "customers",
                "products",
                "orders",
                "order_items",
                "payments",
                "deliveries",
                "returns",
                "tickets",
                "workflow_runs",
                "policy_documents",
                "policy_chunks",
                "action_proposals",
                "approvals",
                "refund_operations",
                "audit_events",
            }
            command.check(config)
            command.downgrade(config, "base")
            assert set(inspect(connection).get_table_names()) == {"alembic_version"}
            command.upgrade(config, "head")
            command.check(config)


def test_monetary_columns_use_database_bigints(migrated_engine) -> None:
    inspector = inspect(migrated_engine)
    checked = 0
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            if column["name"].endswith("_minor"):
                assert isinstance(column["type"], BigInteger), (table, column["name"])
                checked += 1
    assert checked >= 7


def test_cross_tenant_order_reference_is_rejected(db: Session, case) -> None:
    db.add(
        Order(
            tenant_id=uuid4(),
            customer_id=case.customer.id,
            status="paid",
            currency="INR",
            paid_amount_minor=249900,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_ticket_cannot_reference_another_customers_order(db: Session, case) -> None:
    db.add(
        Ticket(
            tenant_id=case.tenant_id,
            customer_id=case.other_customer.id,
            order_id=case.order.id,
            category="refund",
            summary="Invalid access",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_auth_subject_is_unique_per_tenant_but_reusable_across_tenants(db: Session, case) -> None:
    db.add(
        Customer(
            tenant_id=uuid4(),
            external_auth_subject="customer-1",
            name="Other Tenant",
            email="tenant@example.test",
        )
    )
    db.flush()
    db.add(
        Customer(
            tenant_id=case.tenant_id,
            external_auth_subject="customer-1",
            name="Duplicate",
            email="duplicate@example.test",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize("refunded,reserved", [(-1, 0), (0, -1), (249901, 0), (100000, 149901)])
def test_invalid_balance_is_rejected(db: Session, case, refunded: int, reserved: int) -> None:
    case.order.refunded_amount_minor = refunded
    case.order.reserved_amount_minor = reserved
    with pytest.raises(IntegrityError):
        db.flush()


def test_full_reservation_blocks_an_additional_unit(db: Session, case) -> None:
    case.order.reserved_amount_minor = 249900
    db.flush()
    case.order.reserved_amount_minor += 1
    with pytest.raises(IntegrityError):
        db.flush()


def refund(case, **changes) -> RefundOperation:
    values = dict(
        tenant_id=case.tenant_id,
        order_id=case.order.id,
        proposal_id=case.proposal.id,
        amount_minor=249900,
        currency="INR",
        idempotency_key=f"refund:{uuid4()}",
    )
    values.update(changes)
    return RefundOperation(**values)


def test_duplicate_operation_for_a_proposal_is_rejected(db: Session, case) -> None:
    db.add(refund(case))
    db.flush()
    db.add(refund(case))
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_idempotency_key_cannot_be_reused_for_another_proposal(db: Session, case) -> None:
    first = refund(case, idempotency_key="stable-refund-key")
    db.add(first)
    db.flush()
    second_proposal = case.proposal_factory()
    db.add(refund(case, proposal_id=second_proposal.id, idempotency_key="stable-refund-key"))
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "changes", [{"amount_minor": 249901}, {"order_id": uuid4()}, {"tenant_id": uuid4()}]
)
def test_refund_cannot_change_the_proposals_amount_order_or_tenant(
    db: Session, case, changes
) -> None:
    db.add(refund(case, **changes))
    with pytest.raises(IntegrityError):
        db.flush()


def test_approval_must_bind_to_exact_proposal_hash(db: Session, case) -> None:
    proposal = case.proposal_factory()
    db.add(
        Approval(
            tenant_id=case.tenant_id,
            proposal_id=proposal.id,
            payload_hash="b" * 64,
            expires_at=case.now + timedelta(hours=24),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize("reviewer,decided", [(None, True), ("reviewer-1", False)])
def test_decision_requires_reviewer_and_timestamp(db: Session, case, reviewer, decided) -> None:
    case.approval.decision = "approved"
    case.approval.reviewer_id = reviewer
    case.approval.decided_at = case.now + timedelta(seconds=1) if decided else None
    with pytest.raises(IntegrityError):
        db.flush()


def test_decision_at_expiry_is_invalid(db: Session, case) -> None:
    case.approval.decision = "approved"
    case.approval.reviewer_id = "reviewer-1"
    case.approval.decided_at = case.approval.expires_at
    with pytest.raises(IntegrityError):
        db.flush()


def test_recorded_approval_cannot_be_reversed(db: Session, case) -> None:
    case.approval.decision = "approved"
    case.approval.reviewer_id = "reviewer-1"
    case.approval.decided_at = case.now + timedelta(seconds=1)
    db.flush()
    case.approval.decision = "rejected"
    with pytest.raises(IntegrityError):
        db.flush()


def test_proposal_payload_is_immutable_even_through_direct_sql(db: Session, case) -> None:
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE action_proposals SET payload = '{}'::jsonb WHERE id = :id"),
            {"id": case.proposal.id},
        )


def test_proposal_status_can_change_without_changing_contents(db: Session, case) -> None:
    original_payload = dict(case.proposal.payload)
    case.proposal.status = "approved"
    db.flush()
    db.refresh(case.proposal)
    assert case.proposal.payload == original_payload
    assert case.proposal.status == "approved"


@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
def test_audit_history_is_append_only_in_postgres(db: Session, case, operation: str) -> None:
    db.add(
        AuditEvent(
            tenant_id=case.tenant_id,
            run_id=case.proposal.run_id,
            actor="reviewer-1",
            event_type="test_event",
        )
    )
    db.flush()
    statements = {
        "update": "UPDATE audit_events SET actor = 'changed'",
        "delete": "DELETE FROM audit_events",
        "truncate": "TRUNCATE audit_events",
    }
    with pytest.raises(IntegrityError):
        db.execute(text(statements[operation]))


def test_refund_request_key_cannot_change_after_persistence(db: Session, case) -> None:
    operation = refund(case)
    db.add(operation)
    db.flush()
    operation.idempotency_key = "different-key"
    with pytest.raises(IntegrityError):
        db.flush()


def test_refund_terminal_state_cannot_be_reopened(db: Session, case) -> None:
    operation = refund(case)
    db.add(operation)
    db.flush()
    operation.status = "succeeded"
    operation.provider_reference = "confirmed-reference"
    db.flush()
    operation.status = "processing"
    with pytest.raises(IntegrityError):
        db.flush()


def test_unknown_refund_can_be_reconciled_to_success(db: Session, case) -> None:
    operation = refund(case, status="pending_reconciliation")
    db.add(operation)
    db.flush()
    operation.status = "succeeded"
    operation.provider_reference = "mock-confirmed"
    db.flush()
    assert (
        db.scalar(select(RefundOperation.status).where(RefundOperation.id == operation.id))
        == "succeeded"
    )


def test_invalid_status_is_rejected_through_direct_sql(db: Session, case) -> None:
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE orders SET status = 'invented' WHERE id = :id"), {"id": case.order.id}
        )


def test_refund_success_requires_a_provider_reference(db: Session, case) -> None:
    db.add(refund(case, status="succeeded"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_provider_reference_cannot_confirm_two_refund_operations(db: Session, case) -> None:
    db.add(refund(case, status="succeeded", provider_reference="same-provider-result"))
    db.flush()
    second = case.proposal_factory()
    db.add(
        refund(
            case,
            proposal_id=second.id,
            status="succeeded",
            provider_reference="same-provider-result",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
