# ruff: noqa: INP001

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.agents import router as agents_router
from app.api.deps import require_org_admin
from app.db.session import get_session
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.users import User
from app.services.organizations import OrganizationContext


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
    ctx: OrganizationContext,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(agents_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_require_org_admin() -> OrganizationContext:
        return ctx

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[require_org_admin] = _override_require_org_admin
    return app


@pytest.mark.asyncio
async def test_get_agent_accepts_uuid_path_params_on_sqlite() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    organization = Organization(id=uuid4(), name="Personal")
    user = User(
        id=uuid4(),
        clerk_user_id="local-admin",
        email="local-admin@example.com",
        name="Local Admin",
        active_organization_id=organization.id,
    )
    member = OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        role="owner",
        all_boards_read=True,
        all_boards_write=True,
    )
    gateway = Gateway(
        id=uuid4(),
        organization_id=organization.id,
        name="Riley Gateway",
        url="http://127.0.0.1:18789",
        workspace_root="/tmp/workspace",
    )
    board = Board(
        id=uuid4(),
        organization_id=organization.id,
        gateway_id=gateway.id,
        name="ACE-Step music pipeline",
        slug="ace-step-music-pipeline",
    )
    agent = Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name="ACE Music Lead",
        status="provisioning",
        openclaw_session_id=f"agent:lead-{board.id}:main",
        is_board_lead=True,
    )
    ctx = OrganizationContext(organization=organization, member=member)
    app = _build_test_app(session_maker, ctx)

    async with session_maker() as session:
        session.add(organization)
        session.add(user)
        session.add(member)
        session.add(gateway)
        session.add(board)
        session.add(agent)
        await session.commit()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/agents/{agent.id}")
    finally:
        await engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(agent.id)
    assert payload["name"] == "ACE Music Lead"
    assert payload["status"] == "provisioning"
