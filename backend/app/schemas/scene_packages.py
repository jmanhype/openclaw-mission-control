"""Scene package schemas for chained FF/LF execution."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SceneElementKind(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"
    VOICE = "voice"


class SceneOutputKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class SceneWorkflowInputTarget(BaseModel):
    node_id: str
    input_name: str = "image"


class SceneElementReference(BaseModel):
    id: str
    kind: SceneElementKind
    root: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneShotPackage(BaseModel):
    id: str
    workflow_api_json: dict[str, Any]
    first_frame_path: str | None = None
    last_frame_path: str | None = None
    first_frame_target: SceneWorkflowInputTarget
    last_frame_target: SceneWorkflowInputTarget | None = None
    chain_previous_terminal_frame: bool = False
    output_kind: SceneOutputKind = SceneOutputKind.VIDEO
    output_node_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScenePackage(BaseModel):
    id: str
    title: str
    output_dir: str
    elements: list[SceneElementReference] = Field(default_factory=list)
    shots: list[SceneShotPackage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_path(cls, path: str | Path) -> "ScenePackage":
        source_path = Path(path)
        raw_text = source_path.read_text(encoding="utf-8")
        if source_path.suffix.lower() == ".json":
            payload = json.loads(raw_text)
        else:
            try:
                import yaml
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "YAML scene packages require PyYAML. Use JSON or install PyYAML."
                ) from exc
            payload = yaml.safe_load(raw_text) or {}
        return cls.model_validate(payload)

    def resolve_output_dir(self, base_dir: str | Path | None = None) -> Path:
        output_dir = Path(self.output_dir)
        if output_dir.is_absolute() or base_dir is None:
            return output_dir
        return Path(base_dir) / output_dir


class SceneShotRun(BaseModel):
    shot_id: str
    prompt_id: str
    output_path: str
    terminal_frame_path: str | None = None
    history: dict[str, Any] = Field(default_factory=dict)


class SceneRunResult(BaseModel):
    scene_id: str
    output_dir: str
    shots: list[SceneShotRun] = Field(default_factory=list)
