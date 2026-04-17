"""Structured studio task packages for reproducible execution evidence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class TaskPackage(QueryModel, table=True):
    """Persistent run package attached to a task."""

    __tablename__ = "task_packages"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("task_id", name="uq_task_packages_task_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    updated_by_agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)

    objective: str | None = None
    acceptance_target: str | None = None
    workflow_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    input_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    reference_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    keyframe_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    parameters: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    intermediate_outputs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    output_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    benchmark_outputs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    qc_checklist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    execution_id: str | None = None
    qc_verdict: str | None = None
    next_step: str | None = None
    blocker: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
