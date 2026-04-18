"""Schemas for structured task packages."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from app.schemas.scene_packages import ScenePackage, SceneRunResult

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class TaskPackageBase(SQLModel):
    """Shared fields for task package payloads."""

    objective: str | None = None
    acceptance_target: str | None = None
    workflow_paths: list[str] = Field(default_factory=list)
    input_paths: list[str] = Field(default_factory=list)
    reference_paths: list[str] = Field(default_factory=list)
    keyframe_paths: list[str] = Field(default_factory=list)
    parameters: dict[str, object] = Field(default_factory=dict)
    intermediate_outputs: list[str] = Field(default_factory=list)
    output_paths: list[str] = Field(default_factory=list)
    benchmark_outputs: list[str] = Field(default_factory=list)
    qc_checklist: list[str] = Field(default_factory=list)
    scene_package: ScenePackage | None = None
    scene_run: SceneRunResult | None = None
    execution_id: str | None = None
    qc_verdict: str | None = None
    next_step: str | None = None
    blocker: str | None = None


class TaskPackageUpsert(TaskPackageBase):
    """Payload for creating or replacing a task package."""


class TaskPackageSceneExecutionRequest(SQLModel):
    """Optional runtime overrides for executing a stored scene package."""

    comfy_base_url: str | None = None
    comfy_host: str | None = None
    comfy_port: int | None = Field(default=None, ge=1, le=65535)
    base_output_dir: str | None = None


class TaskPackageRead(TaskPackageBase):
    """Serialized task package payload."""

    id: UUID
    board_id: UUID
    task_id: UUID
    updated_by_agent_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
