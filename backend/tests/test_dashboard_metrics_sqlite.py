# ruff: noqa: INP001

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.metrics import dashboard_metrics
from app.core.time import utcnow
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.approvals import Approval
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.tasks import Task
from app.models.users import User
from app.services.organizations import OrganizationContext


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


@pytest.mark.asyncio
async def test_dashboard_metrics_supports_sqlite() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    organization_id = uuid4()
    user_id = uuid4()
    gateway_id = uuid4()
    board_id = uuid4()
    now = utcnow()

    async with session_maker() as session:
        organization = Organization(id=organization_id, name="Personal")
        user = User(
            id=user_id,
            clerk_user_id="local-user",
            email="local@example.com",
            name="Local User",
            active_organization_id=organization_id,
        )
        member = OrganizationMember(
            organization_id=organization_id,
            user_id=user_id,
            role="owner",
            all_boards_read=True,
            all_boards_write=True,
        )
        gateway = Gateway(
            id=gateway_id,
            organization_id=organization_id,
            name="Riley Gateway",
            url="http://127.0.0.1:18789",
            workspace_root="/tmp/workspace",
        )
        board = Board(
            id=board_id,
            organization_id=organization_id,
            gateway_id=gateway_id,
            name="ComfyUI video pipeline",
            slug="comfyui-video-pipeline",
        )
        agent = Agent(
            board_id=board_id,
            gateway_id=gateway_id,
            name="Comfy Video Lead",
            status="online",
            last_seen_at=now - timedelta(hours=1),
            is_board_lead=True,
        )
        task_done = Task(
            board_id=board_id,
            title="Proof LTX run",
            status="done",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
        )
        task_review = Task(
            board_id=board_id,
            title="Review Wan clip",
            status="review",
            created_at=now - timedelta(days=1),
            in_progress_at=now - timedelta(hours=5),
            updated_at=now - timedelta(hours=2),
        )
        task_in_progress = Task(
            board_id=board_id,
            title="Tune iPhone look",
            status="in_progress",
            created_at=now - timedelta(hours=10),
            in_progress_at=now - timedelta(hours=9),
            updated_at=now - timedelta(hours=3),
        )
        task_inbox = Task(
            board_id=board_id,
            title="Compare Wan vs LTX",
            status="inbox",
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=4),
        )
        approval = Approval(
            board_id=board_id,
            task_id=task_review.id,
            agent_id=agent.id,
            action_type="run_gpu_job",
            confidence=0.87,
            status="pending",
            created_at=now - timedelta(minutes=30),
        )
        error_event = ActivityEvent(
            board_id=board_id,
            task_id=task_review.id,
            agent_id=agent.id,
            event_type="worker.failed",
            created_at=now - timedelta(hours=1),
        )
        ok_event = ActivityEvent(
            board_id=board_id,
            task_id=task_review.id,
            agent_id=agent.id,
            event_type="task.updated",
            created_at=now - timedelta(hours=1, minutes=15),
        )

        session.add(organization)
        session.add(user)
        session.add(member)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        session.add(task_done)
        session.add(task_review)
        session.add(task_in_progress)
        session.add(task_inbox)
        session.add(approval)
        session.add(error_event)
        session.add(ok_event)
        await session.commit()

        ctx = OrganizationContext(organization=organization, member=member)
        metrics = await dashboard_metrics(
            range_key="7d",
            board_id=None,
            group_id=None,
            session=session,
            ctx=ctx,
        )

    try:
        assert metrics.kpis.active_agents == 1
        assert metrics.kpis.inbox_tasks == 1
        assert metrics.kpis.in_progress_tasks == 1
        assert metrics.kpis.review_tasks == 1
        assert metrics.kpis.done_tasks == 1
        assert metrics.kpis.error_rate_pct == pytest.approx(50.0)
        assert metrics.kpis.median_cycle_time_hours_7d == pytest.approx(3.0)
        assert metrics.pending_approvals.total == 1
        assert sum(point.value for point in metrics.throughput.primary.points) == pytest.approx(1.0)
        assert sum(point.value for point in metrics.error_rate.primary.points) == pytest.approx(50.0)
        assert any(point.review == 1 for point in metrics.wip.primary.points)
    finally:
        await engine.dispose()
