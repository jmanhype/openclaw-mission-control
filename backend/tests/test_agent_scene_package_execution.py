from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import agent as agent_api
from app.core.agent_auth import AgentAuthContext
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.task_packages import TaskPackage
from app.models.tasks import Task
from app.schemas.scene_packages import (
    SceneOutputKind,
    ScenePackage,
    SceneShotPackage,
    SceneShotRun,
    SceneRunResult,
    SceneWorkflowInputTarget,
)
from app.schemas.task_packages import TaskPackageRead, TaskPackageSceneExecutionRequest
from app.services.studio import task_package_execution as task_package_execution_service
from app.services.studio.task_package_execution import (
    SceneTaskExecutionActor,
    SceneTaskExecutionError,
    execute_task_scene_package,
)


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _seed_board_task_agent_and_package(
    session: AsyncSession,
) -> tuple[Board, Task, Agent, TaskPackage]:
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
        name="worker",
        status="online",
    )
    task = Task(
        id=uuid4(),
        board_id=board.id,
        title="Task",
        assigned_agent_id=agent.id,
    )
    task_package = TaskPackage(
        board_id=board.id,
        task_id=task.id,
        scene_package=ScenePackage(
            id="scene_001",
            title="Harbor scene",
            output_dir="runs/scene_001",
            shots=[
                SceneShotPackage(
                    id="shot_001",
                    workflow_api_json={"10": {"inputs": {"image": ""}}},
                    first_frame_path="/tmp/first.png",
                    first_frame_target=SceneWorkflowInputTarget(node_id="10"),
                    output_kind=SceneOutputKind.VIDEO,
                )
            ],
        ).model_dump(mode="json"),
        parameters={"comfy_base_url": "http://comfy.local:8188"},
    )
    session.add(Organization(id=organization_id, name=f"org-{organization_id}"))
    session.add(gateway)
    session.add(board)
    session.add(agent)
    session.add(task)
    session.add(task_package)
    await session.commit()
    return board, task, agent, task_package


@pytest.mark.asyncio
async def test_agent_execute_scene_package_persists_scene_run(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            board, task, agent, _task_package = await _seed_board_task_agent_and_package(session)

            async def fake_execute_task_scene_package(**kwargs):
                task_package = await TaskPackage.objects.filter_by(task_id=task.id).first(session)
                assert task_package is not None
                task_package.scene_run = SceneRunResult(
                    scene_id="scene_001",
                    output_dir="runs/scene_001",
                    shots=[
                        SceneShotRun(
                            shot_id="shot_001",
                            prompt_id="prompt-123",
                            output_path="/tmp/output.mp4",
                            terminal_frame_path="/tmp/output_last.png",
                        )
                    ],
                ).model_dump(mode="json")
                task_package.output_paths = ["/tmp/output.mp4"]
                task_package.intermediate_outputs = ["/tmp/output_last.png"]
                session.add(task_package)
                await session.commit()
                await session.refresh(task_package)
                return TaskPackageRead.model_validate(task_package)

            monkeypatch.setattr(agent_api, "execute_task_scene_package", fake_execute_task_scene_package)

            result = await agent_api.execute_scene_package(
                payload=TaskPackageSceneExecutionRequest(),
                task=task,
                session=session,
                agent_ctx=AgentAuthContext(actor_type="agent", agent=agent),
            )

            assert result.scene_run is not None
            assert result.scene_run.shots[0].prompt_id == "prompt-123"
            assert result.output_paths == ["/tmp/output.mp4"]
            assert board.id == result.board_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_agent_execute_scene_package_maps_runner_failure_to_http_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            _board, task, agent, _task_package = await _seed_board_task_agent_and_package(session)

            async def fake_execute_task_scene_package(**kwargs):
                raise SceneTaskExecutionError("comfy down")

            monkeypatch.setattr(agent_api, "execute_task_scene_package", fake_execute_task_scene_package)

            with pytest.raises(HTTPException) as exc:
                await agent_api.execute_scene_package(
                    payload=TaskPackageSceneExecutionRequest(),
                    task=task,
                    session=session,
                    agent_ctx=AgentAuthContext(actor_type="agent", agent=agent),
                )

            assert exc.value.status_code == 502
            assert exc.value.detail == "comfy down"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_non_assigned_worker_cannot_execute_scene_package() -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            _board, task, _agent, _task_package = await _seed_board_task_agent_and_package(session)
            other_agent = Agent(
                id=uuid4(),
                board_id=task.board_id,
                gateway_id=(await session.exec(select(Gateway.id))).first(),
                name="other-worker",
                status="online",
            )
            session.add(other_agent)
            await session.commit()

            with pytest.raises(HTTPException) as exc:
                await agent_api.execute_scene_package(
                    payload=TaskPackageSceneExecutionRequest(),
                    task=task,
                    session=session,
                    agent_ctx=AgentAuthContext(actor_type="agent", agent=other_agent),
                )

            assert exc.value.status_code == 403
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_execute_task_scene_package_persists_scene_run_and_comment(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            _board, task, agent, task_package = await _seed_board_task_agent_and_package(session)
            first_frame = tmp_path / "first.png"
            first_frame.write_bytes(b"first")
            task_package.scene_package = ScenePackage(
                id="scene_001",
                title="Harbor scene",
                output_dir="runs/scene_001",
                shots=[
                    SceneShotPackage(
                        id="shot_001",
                        workflow_api_json={"10": {"inputs": {"image": ""}}},
                        first_frame_path=str(first_frame),
                        first_frame_target=SceneWorkflowInputTarget(node_id="10"),
                        output_kind=SceneOutputKind.VIDEO,
                    )
                ],
            ).model_dump(mode="json")
            session.add(task_package)
            await session.commit()

            class StubClient:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return None

            class StubRunner:
                def __init__(self, client):
                    self.client = client

                async def run(self, scene_package, base_output_dir=None):
                    return SceneRunResult(
                        scene_id=scene_package.id,
                        output_dir=str(tmp_path / "renders"),
                        shots=[
                            SceneShotRun(
                                shot_id="shot_001",
                                prompt_id="prompt-123",
                                output_path=str(tmp_path / "renders/01_shot_001.mp4"),
                                terminal_frame_path=str(tmp_path / "renders/shot_001_last_frame.png"),
                            )
                        ],
                    )

            monkeypatch.setattr(task_package_execution_service, "ScenePackageRunner", StubRunner)

            result = await execute_task_scene_package(
                session=session,
                task=task,
                actor=SceneTaskExecutionActor(agent_id=agent.id, agent_name=agent.name),
                payload=TaskPackageSceneExecutionRequest(),
                client_factory=lambda **kwargs: StubClient(),
            )

            assert result.scene_run is not None
            assert result.scene_run.shots[0].prompt_id == "prompt-123"
            assert result.output_paths[0].endswith("01_shot_001.mp4")
            comments = list(
                await session.exec(
                    select(ActivityEvent).where(ActivityEvent.task_id == task.id).where(
                        ActivityEvent.event_type == "task.comment"
                    )
                )
            )
            assert comments
            assert "Executed scene package" in (comments[-1].message or "")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_execute_task_scene_package_persists_blocker_and_comment_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            _board, task, agent, _task_package = await _seed_board_task_agent_and_package(session)

            class StubClient:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return None

            class FailingRunner:
                def __init__(self, client):
                    self.client = client

                async def run(self, scene_package, base_output_dir=None):
                    raise RuntimeError("broken workflow")

            monkeypatch.setattr(task_package_execution_service, "ScenePackageRunner", FailingRunner)

            with pytest.raises(SceneTaskExecutionError) as exc:
                await execute_task_scene_package(
                    session=session,
                    task=task,
                    actor=SceneTaskExecutionActor(agent_id=agent.id, agent_name=agent.name),
                    payload=TaskPackageSceneExecutionRequest(),
                    client_factory=lambda **kwargs: StubClient(),
                )

            assert "broken workflow" in str(exc.value)
            reloaded = await TaskPackage.objects.filter_by(task_id=task.id).first(session)
            assert reloaded is not None
            assert reloaded.blocker == "broken workflow"
            comments = list(
                await session.exec(
                    select(ActivityEvent).where(ActivityEvent.task_id == task.id).where(
                        ActivityEvent.event_type == "task.comment"
                    )
                )
            )
            assert comments
            assert "Blocked executing scene package" in (comments[-1].message or "")
    finally:
        await engine.dispose()
