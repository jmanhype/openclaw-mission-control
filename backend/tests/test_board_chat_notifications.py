from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import board_group_memory as board_group_memory_api
from app.api import board_memory as board_memory_api
from app.api.deps import ActorContext
from app.models.agents import Agent
from app.models.board_group_memory import BoardGroupMemory
from app.models.board_groups import BoardGroup
from app.models.board_memory import BoardMemory
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.users import User
from app.services.openclaw.gateway_rpc import GatewayConfig as GatewayClientConfig


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_board_chat_notifications_deliver_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    sent: list[dict[str, Any]] = []
    try:
        async with await _make_session(engine) as session:
            org_id = uuid4()
            gateway_id = uuid4()
            board_id = uuid4()
            lead_id = uuid4()
            worker_id = uuid4()

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
            board = Board(
                id=board_id,
                organization_id=org_id,
                name="Video Ops",
                slug="video-ops",
                gateway_id=gateway_id,
            )
            session.add(board)
            session.add(
                User(
                    id=uuid4(),
                    clerk_user_id="user_clerk_1",
                    email="user@example.com",
                    name="Operator",
                ),
            )
            session.add(
                Agent(
                    id=lead_id,
                    board_id=board_id,
                    gateway_id=gateway_id,
                    name="lead",
                    status="online",
                    openclaw_session_id="agent:lead:session",
                    is_board_lead=True,
                ),
            )
            session.add(
                Agent(
                    id=worker_id,
                    board_id=board_id,
                    gateway_id=gateway_id,
                    name="worker",
                    status="online",
                    openclaw_session_id="agent:worker:session",
                ),
            )
            await session.commit()

            actor = ActorContext(
                actor_type="user",
                user=User(
                    id=uuid4(),
                    clerk_user_id="user_clerk_actor",
                    email="actor@example.com",
                    name="Operator",
                ),
            )

            async def _fake_optional_gateway_config_for_board(
                self: board_memory_api.GatewayDispatchService,
                target_board: Board,
            ) -> GatewayClientConfig:
                _ = self
                return GatewayClientConfig(
                    url=f"ws://gateway.example/ws/{target_board.id}",
                    token=None,
                )

            async def _fake_try_send_agent_message(
                self: board_memory_api.GatewayDispatchService,
                **kwargs: Any,
            ) -> None:
                _ = self
                sent.append(kwargs)
                return None

            monkeypatch.setattr(
                board_memory_api.GatewayDispatchService,
                "optional_gateway_config_for_board",
                _fake_optional_gateway_config_for_board,
            )
            monkeypatch.setattr(
                board_memory_api.GatewayDispatchService,
                "try_send_agent_message",
                _fake_try_send_agent_message,
            )

            await board_memory_api._notify_chat_targets(
                session=session,
                board=board,
                memory=BoardMemory(
                    board_id=board_id,
                    content="@worker run the next proof.",
                    is_chat=True,
                    tags=["chat"],
                ),
                actor=actor,
            )

        assert len(sent) == 2
        assert {item["agent_name"] for item in sent} == {"lead", "worker"}
        assert all(item["deliver"] is True for item in sent)
        worker_message = next(item["message"] for item in sent if item["agent_name"] == "worker")
        lead_message = next(item["message"] for item in sent if item["agent_name"] == "lead")
        assert "BOARD CHAT MENTION" in worker_message
        assert "BOARD CHAT" in lead_message
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_board_group_chat_notifications_deliver_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    sent: list[dict[str, Any]] = []
    try:
        async with await _make_session(engine) as session:
            org_id = uuid4()
            gateway_id = uuid4()
            group_id = uuid4()
            board_id = uuid4()

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
            group = BoardGroup(
                id=group_id,
                organization_id=org_id,
                name="Video Group",
                slug="video-group",
            )
            board = Board(
                id=board_id,
                organization_id=org_id,
                name="Video Ops",
                slug="video-ops",
                gateway_id=gateway_id,
                board_group_id=group_id,
            )
            session.add(group)
            session.add(board)
            session.add(
                Agent(
                    id=uuid4(),
                    board_id=board_id,
                    gateway_id=gateway_id,
                    name="lead",
                    status="online",
                    openclaw_session_id="agent:lead:session",
                    is_board_lead=True,
                ),
            )
            session.add(
                Agent(
                    id=uuid4(),
                    board_id=board_id,
                    gateway_id=gateway_id,
                    name="worker",
                    status="online",
                    openclaw_session_id="agent:worker:session",
                ),
            )
            await session.commit()

            actor = ActorContext(
                actor_type="user",
                user=User(
                    id=uuid4(),
                    clerk_user_id="user_clerk_actor",
                    email="actor@example.com",
                    name="Operator",
                ),
            )

            async def _fake_optional_gateway_config_for_board(
                self: board_group_memory_api.GatewayDispatchService,
                target_board: Board,
            ) -> GatewayClientConfig:
                _ = self
                return GatewayClientConfig(
                    url=f"ws://gateway.example/ws/{target_board.id}",
                    token=None,
                )

            async def _fake_try_send_agent_message(
                self: board_group_memory_api.GatewayDispatchService,
                **kwargs: Any,
            ) -> None:
                _ = self
                sent.append(kwargs)
                return None

            monkeypatch.setattr(
                board_group_memory_api.GatewayDispatchService,
                "optional_gateway_config_for_board",
                _fake_optional_gateway_config_for_board,
            )
            monkeypatch.setattr(
                board_group_memory_api.GatewayDispatchService,
                "try_send_agent_message",
                _fake_try_send_agent_message,
            )

            await board_group_memory_api._notify_group_memory_targets(
                session=session,
                group=group,
                memory=BoardGroupMemory(
                    board_group_id=group_id,
                    content="@worker sync the first segment proof.",
                    is_chat=True,
                    tags=["chat"],
                ),
                actor=actor,
            )

        assert len(sent) == 2
        assert {item["agent_name"] for item in sent} == {"lead", "worker"}
        assert all(item["deliver"] is True for item in sent)
        worker_message = next(item["message"] for item in sent if item["agent_name"] == "worker")
        lead_message = next(item["message"] for item in sent if item["agent_name"] == "lead")
        assert "GROUP CHAT MENTION" in worker_message
        assert "GROUP CHAT" in lead_message
    finally:
        await engine.dispose()
