import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.db.models import (
    ActionProposal,
    Approval,
    Customer,
    Order,
    PolicyDocument,
    Ticket,
    WorkflowRun,
)
from tests.integration.helpers import migration_config


@pytest.fixture(scope="session")
def schema_factory():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL schema integration tests")

    @contextmanager
    def create_schema() -> Iterator[Engine]:
        # A generated schema isolates every migration test from application/public data.
        name = f"test_schema_{uuid4().hex}"
        control = create_engine(url, connect_args={"connect_timeout": 3})
        with control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{name}"'))
        engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={name}", "connect_timeout": 3},
        )
        try:
            yield engine
        finally:
            engine.dispose()
            with control.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
            control.dispose()

    return create_schema


@pytest.fixture(scope="session")
def migrated_engine(schema_factory) -> Iterator[Engine]:
    with schema_factory() as engine:
        with engine.begin() as connection:
            command.upgrade(migration_config(connection), "head")
        yield engine


@pytest.fixture
def db(migrated_engine: Engine) -> Iterator[Session]:
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            try:
                yield session
            finally:
                session.rollback()
                transaction.rollback()


@pytest.fixture
def case(db: Session) -> SimpleNamespace:
    now = datetime.now(UTC)
    tenant_id = uuid4()
    customer = Customer(
        tenant_id=tenant_id,
        external_auth_subject="customer-1",
        name="Synthetic Customer",
        email="customer@example.test",
    )
    other = Customer(
        tenant_id=tenant_id,
        external_auth_subject="customer-2",
        name="Other Customer",
        email="other@example.test",
    )
    db.add_all([customer, other])
    db.flush()
    order = Order(
        tenant_id=tenant_id,
        customer_id=customer.id,
        status="delivered",
        currency="INR",
        paid_amount_minor=249900,
        delivered_at=now - timedelta(days=10),
    )
    policy = PolicyDocument(
        tenant_id=tenant_id,
        name="refund",
        version="v1",
        effective_from=now - timedelta(days=365),
        source_uri="synthetic:refund-v1",
    )
    db.add_all([order, policy])
    db.flush()
    ticket = Ticket(
        tenant_id=tenant_id,
        customer_id=customer.id,
        order_id=order.id,
        category="refund",
        summary="Returned headphones",
    )
    db.add(ticket)
    db.flush()

    def proposal_factory() -> ActionProposal:
        run = WorkflowRun(tenant_id=tenant_id, ticket_id=ticket.id, order_id=order.id)
        db.add(run)
        db.flush()
        proposal = ActionProposal(
            tenant_id=tenant_id,
            run_id=run.id,
            order_id=order.id,
            amount_minor=249900,
            currency="INR",
            policy_document_id=policy.id,
            payload={"amount_minor": 249900},
            payload_hash="a" * 64,
        )
        db.add(proposal)
        db.flush()
        return proposal

    proposal = proposal_factory()
    approval = Approval(
        tenant_id=tenant_id,
        proposal_id=proposal.id,
        payload_hash=proposal.payload_hash,
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )
    db.add(approval)
    db.flush()
    return SimpleNamespace(
        tenant_id=tenant_id,
        customer=customer,
        other_customer=other,
        order=order,
        ticket=ticket,
        policy=policy,
        proposal=proposal,
        approval=approval,
        now=now,
        proposal_factory=proposal_factory,
    )
