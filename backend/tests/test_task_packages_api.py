from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import tasks as tasks_api
from app.api.deps import ActorContext
from app.models.agents import Agent
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.task_packages import TaskPackage
from app.models.tasks import Task
from app.models.boards import Board
from app.schemas.scene_packages import (
    SceneOutputKind,
    ScenePackage,
    SceneRunResult,
    SceneShotPackage,
    SceneShotRun,
    SceneWorkflowInputTarget,
)
from app.schemas.task_packages import TaskPackageUpsert


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _seed_board_task_and_agent(session: AsyncSession) -> tuple[Board, Task, Agent]:
    organization_id = uuid4()
    gateway = Gateway(
        id=uuid4(),
        organization_id=organization_id,
        name="gateway",
        url="https://gateway.local",
        workspace_root="/tmp/workspace",
    )
    board = Board(
        id=uuid4(),
        organization_id=organization_id,
        gateway_id=gateway.id,
        name="board",
        slug=f"board-{uuid4()}",
    )
    agent = Agent(
        id=uuid4(),
        board_id=board.id,
        gateway_id=gateway.id,
        name="agent",
        status="online",
    )
    task = Task(
        id=uuid4(),
        board_id=board.id,
        title="Task",
        assigned_agent_id=agent.id,
    )
    session.add(Organization(id=organization_id, name=f"org-{organization_id}"))
    session.add(gateway)
    session.add(board)
    session.add(agent)
    session.add(task)
    await session.commit()
    return board, task, agent


@pytest.mark.asyncio
async def test_upsert_task_package_creates_and_reads_package() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            board, task, agent = await _seed_board_task_and_agent(session)
            payload = TaskPackageUpsert(
                objective="Produce one reusable Wan 2.2 proof run",
                workflow_paths=["/workflows/video_wan2_2_5B_ti2v_reddit_bald_man.api.json"],
                input_paths=["/input/elder_man.jpg"],
                output_paths=["/output/wan22/elder_man_00001_.mp4"],
                scene_package=ScenePackage(
                    id="scene_001",
                    title="Bus arrival",
                    output_dir="runs/scene_001",
                    shots=[
                        SceneShotPackage(
                            id="shot_001",
                            workflow_api_json={"10": {"inputs": {"image": ""}}},
                            first_frame_path="/input/shot_001_first.png",
                            first_frame_target=SceneWorkflowInputTarget(node_id="10"),
                            output_kind=SceneOutputKind.VIDEO,
                        )
                    ],
                ),
                scene_run=SceneRunResult(
                    scene_id="scene_001",
                    output_dir="runs/scene_001",
                    shots=[
                        SceneShotRun(
                            shot_id="shot_001",
                            prompt_id="prompt-123",
                            output_path="/output/wan22/elder_man_00001_.mp4",
                            terminal_frame_path="/output/wan22/elder_man_00001_last.png",
                        )
                    ],
                ),
                execution_id="prompt-123",
                qc_verdict="pass",
                next_step="Promote baseline",
            )

            created = await tasks_api.upsert_task_package(
                payload=payload,
                task=task,
                session=session,
                actor=ActorContext(actor_type="agent", agent=agent),
            )

            fetched = await tasks_api.get_task_package(
                task=task,
                session=session,
                _actor=ActorContext(actor_type="agent", agent=agent),
            )

            assert created.id == fetched.id
            assert created.board_id == board.id
            assert created.task_id == task.id
            assert created.updated_by_agent_id == agent.id
            assert created.workflow_paths == payload.workflow_paths
            assert created.output_paths == payload.output_paths
            assert created.scene_package is not None
            assert created.scene_package.id == "scene_001"
            assert created.scene_package.shots[0].first_frame_target.node_id == "10"
            assert created.scene_run is not None
            assert created.scene_run.shots[0].terminal_frame_path is not None
            assert created.execution_id == "prompt-123"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_task_package_updates_existing_record_without_duplication() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            _board, task, agent = await _seed_board_task_and_agent(session)

            first = await tasks_api.upsert_task_package(
                payload=TaskPackageUpsert(
                    workflow_paths=["/workflows/first.json"],
                    output_paths=["/output/first.mp4"],
                    qc_verdict="pending",
                ),
                task=task,
                session=session,
                actor=ActorContext(actor_type="agent", agent=agent),
            )

            second = await tasks_api.upsert_task_package(
                payload=TaskPackageUpsert(
                    workflow_paths=["/workflows/second.json"],
                    output_paths=["/output/final.mp4"],
                    qc_verdict="pass",
                    blocker="none",
                ),
                task=task,
                session=session,
                actor=ActorContext(actor_type="agent", agent=agent),
            )

            packages = list(await session.exec(select(TaskPackage).where(TaskPackage.task_id == task.id)))

            assert first.id == second.id
            assert len(packages) == 1
            assert second.workflow_paths == ["/workflows/second.json"]
            assert second.output_paths == ["/output/final.mp4"]
            assert second.qc_verdict == "pass"
            assert second.blocker == "none"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_task_package_raises_404_when_missing() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            _board, task, agent = await _seed_board_task_and_agent(session)

            with pytest.raises(HTTPException) as exc:
                await tasks_api.get_task_package(
                    task=task,
                    session=session,
                    _actor=ActorContext(actor_type="agent", agent=agent),
                )

            assert exc.value.status_code == 404
            assert exc.value.detail == "Task package not found."
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_task_and_related_records_deletes_task_package() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            board, task, agent = await _seed_board_task_and_agent(session)
            package = TaskPackage(
                board_id=board.id,
                task_id=task.id,
                updated_by_agent_id=agent.id,
                workflow_paths=["/workflows/run.json"],
            )
            session.add(package)
            await session.commit()

            await tasks_api.delete_task_and_related_records(session, task=task)

            remaining = list(await session.exec(select(TaskPackage).where(TaskPackage.task_id == task.id)))
            assert remaining == []
    finally:
        await engine.dispose()
