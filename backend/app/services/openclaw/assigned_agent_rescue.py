"""Recover board agents that went offline while still owning active work."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.session import async_session_maker
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.tasks import Task
from app.services.openclaw.constants import OFFLINE_AFTER
from app.services.openclaw.lifecycle_orchestrator import AgentLifecycleOrchestrator

logger = get_logger(__name__)
_ACTIVE_ASSIGNED_TASK_STATUSES: Final[tuple[str, ...]] = ("in_progress", "review")
_IGNORED_AGENT_STATUSES: Final[frozenset[str]] = frozenset({"deleting", "updating"})

_SessionFactory = Callable[[], AsyncSession]


def _is_effectively_offline(agent: Agent, *, now: datetime | None = None) -> bool:
    current = now or utcnow()
    if agent.status == "offline":
        return True
    if agent.last_seen_at is None:
        return True
    return current - agent.last_seen_at > OFFLINE_AFTER


def _cooldown_elapsed(
    agent: Agent,
    *,
    cooldown: timedelta,
    now: datetime | None = None,
) -> bool:
    current = now or utcnow()
    if agent.last_wake_sent_at is None:
        return True
    return current - agent.last_wake_sent_at >= cooldown


def _should_attempt_assigned_agent_rescue(
    agent: Agent,
    *,
    cooldown: timedelta,
    now: datetime | None = None,
) -> bool:
    current = now or utcnow()
    if agent.board_id is None:
        return False
    if agent.status in _IGNORED_AGENT_STATUSES:
        return False
    if not _is_effectively_offline(agent, now=current):
        return False
    if agent.checkin_deadline_at is not None and current < agent.checkin_deadline_at:
        return False
    return _cooldown_elapsed(agent, cooldown=cooldown, now=current)


async def _assigned_board_agent_ids(
    session: AsyncSession,
    *,
    limit: int | None,
) -> list[UUID]:
    statement = (
        select(Agent.id)
        .join(Task, col(Task.assigned_agent_id) == col(Agent.id))
        .where(col(Agent.board_id).is_not(None))
        .where(col(Task.status).in_(_ACTIVE_ASSIGNED_TASK_STATUSES))
        .distinct()
    )
    ids = list(await session.exec(statement))
    if limit is None or limit < 1:
        return ids
    return ids[:limit]


async def rescue_stranded_assigned_agents(
    *,
    session_factory: _SessionFactory = async_session_maker,
    cooldown: timedelta | None = None,
    limit: int | None = None,
) -> int:
    """Re-run lifecycle for offline board agents that still own active work."""

    current = utcnow()
    cooldown_window = cooldown or timedelta(
        seconds=settings.assigned_agent_rescue_cooldown_seconds,
    )
    rescued = 0

    async with session_factory() as session:
        agent_ids = await _assigned_board_agent_ids(session, limit=limit)
        if not agent_ids:
            return 0

        orchestrator = AgentLifecycleOrchestrator(session)
        for agent_id in agent_ids:
            agent = await Agent.objects.by_id(agent_id).first(session)
            if agent is None:
                continue
            if not _should_attempt_assigned_agent_rescue(
                agent,
                cooldown=cooldown_window,
                now=current,
            ):
                continue

            gateway = await Gateway.objects.by_id(agent.gateway_id).first(session)
            if gateway is None:
                logger.warning(
                    "assigned_agent_rescue.skip_missing_gateway",
                    extra={"agent_id": str(agent.id), "gateway_id": str(agent.gateway_id)},
                )
                continue

            board: Board | None = None
            if agent.board_id is not None:
                board = await Board.objects.by_id(agent.board_id).first(session)
            if board is None:
                logger.warning(
                    "assigned_agent_rescue.skip_missing_board",
                    extra={"agent_id": str(agent.id), "board_id": str(agent.board_id)},
                )
                continue

            if agent.last_wake_sent_at is not None:
                agent.wake_attempts = 0
                agent.checkin_deadline_at = None
                session.add(agent)
                await session.flush()

            try:
                await orchestrator.run_lifecycle(
                    gateway=gateway,
                    agent_id=agent.id,
                    board=board,
                    user=None,
                    action="update",
                    auth_token=None,
                    force_bootstrap=False,
                    reset_session=True,
                    wake=True,
                    deliver_wakeup=True,
                    wakeup_verb="updated",
                    clear_confirm_token=True,
                    raise_gateway_errors=False,
                )
            except Exception:
                await session.rollback()
                logger.exception(
                    "assigned_agent_rescue.failed",
                    extra={"agent_id": str(agent.id), "board_id": str(board.id)},
                )
                continue

            rescued += 1
            logger.warning(
                "assigned_agent_rescue.retriggered",
                extra={
                    "agent_id": str(agent.id),
                    "board_id": str(board.id),
                    "task_statuses": list(_ACTIVE_ASSIGNED_TASK_STATUSES),
                },
            )

    return rescued
