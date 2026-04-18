"""Execute stored task-package scene payloads inside Paperclip."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.task_packages import TaskPackage
from app.models.tasks import Task
from app.schemas.scene_packages import ScenePackage
from app.schemas.task_packages import TaskPackageRead, TaskPackageSceneExecutionRequest
from app.services.activity_log import record_activity
from app.services.studio.comfyui import ComfyUIClient
from app.services.studio.scene_package_runner import ScenePackageRunner


@dataclass(frozen=True)
class SceneTaskExecutionActor:
    """Minimal actor payload needed for task-package execution."""

    agent_id: object | None
    agent_name: str


ClientFactory = Callable[..., ComfyUIClient]


class SceneTaskExecutionError(RuntimeError):
    """Raised when a task package scene run fails after persistence."""


async def execute_task_scene_package(
    *,
    session: AsyncSession,
    task: Task,
    actor: SceneTaskExecutionActor,
    payload: TaskPackageSceneExecutionRequest,
    client_factory: ClientFactory = ComfyUIClient,
) -> TaskPackageRead:
    task_package = await TaskPackage.objects.filter_by(task_id=task.id).first(session)
    if task_package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task package not found.")
    if task_package.scene_package is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Task package does not contain a scene_package.",
        )

    scene_package = ScenePackage.model_validate(task_package.scene_package)
    client_kwargs = _resolve_client_kwargs(task_package.parameters, payload)
    base_output_dir = _resolve_base_output_dir(task_package.parameters, payload)

    try:
        async with client_factory(**client_kwargs) as client:
            runner = ScenePackageRunner(client)
            scene_run = await runner.run(scene_package, base_output_dir=base_output_dir)
    except Exception as exc:
        blocker = str(exc).strip() or exc.__class__.__name__
        task_package.blocker = blocker
        task_package.updated_by_agent_id = actor.agent_id
        task_package.updated_at = utcnow()
        session.add(task_package)
        _record_task_comment(
            session=session,
            task=task,
            actor=actor,
            message=_failure_comment(
                scene_package_id=scene_package.id,
                blocker=blocker,
                comfy_target=_format_comfy_target(client_kwargs),
            ),
        )
        await session.commit()
        await session.refresh(task_package)
        raise SceneTaskExecutionError(blocker) from exc

    task_package.scene_run = scene_run.model_dump(mode="json")
    task_package.output_paths = [shot.output_path for shot in scene_run.shots]
    task_package.intermediate_outputs = [
        shot.terminal_frame_path for shot in scene_run.shots if shot.terminal_frame_path
    ]
    if scene_run.shots:
        task_package.execution_id = scene_run.shots[-1].prompt_id
    task_package.blocker = None
    task_package.updated_by_agent_id = actor.agent_id
    task_package.updated_at = utcnow()
    session.add(task_package)
    _record_task_comment(
        session=session,
        task=task,
        actor=actor,
        message=_success_comment(
            scene_package_id=scene_package.id,
            prompt_ids=[shot.prompt_id for shot in scene_run.shots],
            output_paths=[shot.output_path for shot in scene_run.shots],
            comfy_target=_format_comfy_target(client_kwargs),
        ),
    )
    await session.commit()
    await session.refresh(task_package)
    return TaskPackageRead.model_validate(task_package)


def _resolve_client_kwargs(
    parameters: dict[str, object],
    payload: TaskPackageSceneExecutionRequest,
) -> dict[str, Any]:
    comfy_base_url = payload.comfy_base_url or _string_param(parameters, "comfy_base_url")
    if comfy_base_url:
        return {"host": comfy_base_url}
    comfy_host = payload.comfy_host or _string_param(parameters, "comfy_host") or "127.0.0.1"
    comfy_port = payload.comfy_port or _int_param(parameters, "comfy_port") or 8188
    return {"host": comfy_host, "port": comfy_port}


def _resolve_base_output_dir(
    parameters: dict[str, object],
    payload: TaskPackageSceneExecutionRequest,
) -> str | None:
    return payload.base_output_dir or _string_param(parameters, "base_output_dir")


def _string_param(parameters: dict[str, object], key: str) -> str | None:
    value = parameters.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _int_param(parameters: dict[str, object], key: str) -> int | None:
    value = parameters.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _record_task_comment(
    *,
    session: AsyncSession,
    task: Task,
    actor: SceneTaskExecutionActor,
    message: str,
) -> None:
    record_activity(
        session,
        event_type="task.comment",
        message=message,
        task_id=task.id,
        board_id=task.board_id,
        agent_id=actor.agent_id,
    )


def _success_comment(
    *,
    scene_package_id: str,
    prompt_ids: list[str],
    output_paths: list[str],
    comfy_target: str,
) -> str:
    prompt_lines = "\n".join(f"- `{prompt_id}`" for prompt_id in prompt_ids) or "- none"
    output_lines = "\n".join(f"- `{path}`" for path in output_paths) or "- none"
    return (
        "**Update**\n"
        f"- Executed scene package `{scene_package_id}`.\n\n"
        "**Evidence**\n"
        f"- Comfy target: `{comfy_target}`\n"
        f"- Prompt ids:\n{prompt_lines}\n"
        f"- Outputs:\n{output_lines}\n\n"
        "**Next**\n"
        "- QC the latest scene outputs against acceptance criteria."
    )


def _failure_comment(
    *,
    scene_package_id: str,
    blocker: str,
    comfy_target: str,
) -> str:
    return (
        "**Update**\n"
        f"- Blocked executing scene package `{scene_package_id}`: {blocker}\n\n"
        "**Evidence**\n"
        f"- Comfy target: `{comfy_target}`\n\n"
        "**Next**\n"
        "- Fix the blocker and rerun the scene package."
    )


def _format_comfy_target(client_kwargs: dict[str, Any]) -> str:
    host = client_kwargs.get("host", "127.0.0.1")
    port = client_kwargs.get("port")
    if port is None or str(host).startswith(("http://", "https://")):
        return str(host)
    return f"{host}:{port}"
