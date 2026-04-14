# ruff: noqa: INP001

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_board_or_404
from app.db.session import get_session
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _build_app(session_maker: async_sessionmaker[AsyncSession]) -> FastAPI:
    app = FastAPI()

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    @app.get("/boards/{board_id}")
    async def read_board(board: Board = Depends(get_board_or_404)) -> dict[str, str]:
        return {"id": str(board.id), "name": board.name}

    app.dependency_overrides[get_session] = _override_get_session
    return app


@pytest.mark.asyncio
async def test_get_board_or_404_accepts_uuid_path_params_on_sqlite() -> None:
    engine = await _make_engine()
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app = _build_app(session_maker)

    organization_id = uuid4()
    gateway_id = uuid4()
    board_id = uuid4()

    async with session_maker() as session:
        session.add(Organization(id=organization_id, name="Personal"))
        session.add(
            Gateway(
                id=gateway_id,
                organization_id=organization_id,
                name="gateway",
                url="http://127.0.0.1:18789",
                workspace_root="/tmp/workspace",
            ),
        )
        session.add(
            Board(
                id=board_id,
                organization_id=organization_id,
                gateway_id=gateway_id,
                name="ComfyUI video pipeline",
                slug="comfyui-video-pipeline",
            ),
        )
        await session.commit()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/boards/{board_id}")
    finally:
        await engine.dispose()

    assert response.status_code == 200
    assert response.json() == {
        "id": str(board_id),
        "name": "ComfyUI video pipeline",
    }
