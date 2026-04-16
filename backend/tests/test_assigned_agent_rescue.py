# ruff: noqa: S101
"""Tests for recovering offline agents that still own active work."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.services.openclaw.assigned_agent_rescue as assigned_agent_rescue
from app.core.time import utcnow
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.tasks import Task


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _agent_for_rescue(**overrides: object) -> Agent:
    now = utcnow()
    payload = {
        "id": uuid4(),
        "name": "board-agent",
        "board_id": uuid4(),
        "gateway_id": uuid4(),
        "status": "offline",
        "last_seen_at": now - timedelta(minutes=20),
        "last_wake_sent_at": now - timedelta(minutes=10),
        "checkin_deadline_at": None,
    }
    payload.update(overrides)
    return Agent(**payload)


def test_should_attempt_assigned_agent_rescue_skips_active_recovery_window() -> None:
    now = utcnow()
    agent = _agent_for_rescue(
        status="online",
        last_seen_at=now - timedelta(minutes=20),
        last_wake_sent_at=now - timedelta(seconds=15),
        checkin_deadline_at=now + timedelta(seconds=15),
    )

    assert (
        assigned_agent_rescue._should_attempt_assigned_agent_rescue(
            agent,
            cooldown=timedelta(minutes=5),
            now=now,
        )
        is False
    )


def test_should_attempt_assigned_agent_rescue_allows_expired_cycle_after_cooldown() -> None:
    now = utcnow()
    agent = _agent_for_rescue(
        status="online",
        last_seen_at=now - timedelta(minutes=20),
        last_wake_sent_at=now - timedelta(minutes=10),
        checkin_deadline_at=now - timedelta(minutes=9),
    )

    assert (
        assigned_agent_rescue._should_attempt_assigned_agent_rescue(
            agent,
            cooldown=timedelta(minutes=5),
            now=now,
        )
        is True
    )


@pytest.mark.asyncio
async def test_rescue_stranded_assigned_agents_retriggers_stale_assignee(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = utcnow()
    org_id = uuid4()
    gateway_id = uuid4()
    board_id = uuid4()
    agent_id = uuid4()
    task_id = uuid4()
    captured: list[dict[str, object]] = []

    async def _fake_run_lifecycle(
        self: assigned_agent_rescue.AgentLifecycleOrchestrator,
        **kwargs: object,
    ) -> Agent:
        agent = await Agent.objects.by_id(kwargs["agent_id"]).first(self.session)
        assert agent is not None
        captured.append(
            {
                "agent_id": agent.id,
                "wake_attempts": agent.wake_attempts,
                "reset_session": kwargs["reset_session"],
                "board_id": kwargs["board"].id if kwargs["board"] is not None else None,
            }
        )
        return agent

    monkeypatch.setattr(
        assigned_agent_rescue.AgentLifecycleOrchestrator,
        "run_lifecycle",
        _fake_run_lifecycle,
    )

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
                    last_seen_at=now - timedelta(minutes=20),
                    wake_attempts=3,
                    last_wake_sent_at=now - timedelta(minutes=10),
                ),
            )
            session.add(
                Task(
                    id=task_id,
                    board_id=board_id,
                    title="stuck task",
                    status="in_progress",
                    assigned_agent_id=agent_id,
                ),
            )
            await session.commit()

        rescued = await assigned_agent_rescue.rescue_stranded_assigned_agents(
            session_factory=session_maker,
            cooldown=timedelta(minutes=5),
        )
    finally:
        await engine.dispose()

    assert rescued == 1
    assert captured == [
        {
            "agent_id": agent_id,
            "wake_attempts": 0,
            "reset_session": True,
            "board_id": board_id,
        }
    ]
