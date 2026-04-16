# ruff: noqa: S101
"""Tests for lifecycle orchestrator failure unwinding."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.services.openclaw.lifecycle_orchestrator as lifecycle_orchestrator
from app.core.time import utcnow
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.services.openclaw.constants import CHECKIN_DEADLINE_AFTER_WAKE
from app.services.openclaw.gateway_rpc import OpenClawGatewayError


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


@pytest.mark.asyncio
@pytest.mark.parametrize("raise_gateway_errors", [False, True])
async def test_run_lifecycle_gateway_error_restores_agent_state(
    monkeypatch: pytest.MonkeyPatch,
    raise_gateway_errors: bool,
) -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _fake_apply_agent_lifecycle(
        self: lifecycle_orchestrator.OpenClawGatewayProvisioner,
        **_kwargs: object,
    ) -> None:
        _ = self
        raise OpenClawGatewayError("cli parser exploded")

    monkeypatch.setattr(
        lifecycle_orchestrator.OpenClawGatewayProvisioner,
        "apply_agent_lifecycle",
        _fake_apply_agent_lifecycle,
    )

    now = utcnow()
    org_id = uuid4()
    gateway_id = uuid4()
    board_id = uuid4()
    agent_id = uuid4()

    try:
        async with session_maker() as session:
            session.add(Organization(id=org_id, name="org"))
            session.add(
                Gateway(
                    id=gateway_id,
                    organization_id=org_id,
                    name="gateway",
                    url="https://gateway.local",
                    workspace_root="/tmp/workspace",
                ),
            )
            session.add(
                Board(
                    id=board_id,
                    organization_id=org_id,
                    name="board",
                    slug="board",
                    gateway_id=gateway_id,
                ),
            )
            session.add(
                Agent(
                    id=agent_id,
                    name="lead",
                    board_id=board_id,
                    gateway_id=gateway_id,
                    status="online",
                    last_seen_at=now,
                ),
            )
            await session.commit()

            gateway = await Gateway.objects.by_id(gateway_id).first(session)
            board = await Board.objects.by_id(board_id).first(session)
            assert gateway is not None
            assert board is not None

            orchestrator = lifecycle_orchestrator.AgentLifecycleOrchestrator(session)
            if raise_gateway_errors:
                with pytest.raises(HTTPException) as exc_info:
                    await orchestrator.run_lifecycle(
                        gateway=gateway,
                        agent_id=agent_id,
                        board=board,
                        user=None,
                        action="update",
                        wake=True,
                        raise_gateway_errors=True,
                    )
                assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
                assert "Gateway update failed: cli parser exploded" in str(exc_info.value.detail)
            else:
                recovered = await orchestrator.run_lifecycle(
                    gateway=gateway,
                    agent_id=agent_id,
                    board=board,
                    user=None,
                    action="update",
                    wake=True,
                    raise_gateway_errors=False,
                )
                assert recovered.id == agent_id

            agent = await Agent.objects.by_id(agent_id).first(session)
            assert agent is not None
            assert agent.status == "online"
            assert agent.provision_requested_at is None
            assert agent.provision_action is None
            assert agent.last_provision_error == "cli parser exploded"
            assert agent.lifecycle_generation == 1
            assert agent.wake_attempts == 1
            assert agent.last_wake_sent_at is not None
            assert agent.checkin_deadline_at is not None
            assert agent.checkin_deadline_at - agent.last_wake_sent_at <= (
                CHECKIN_DEADLINE_AFTER_WAKE + timedelta(seconds=1)
            )
    finally:
        await engine.dispose()
