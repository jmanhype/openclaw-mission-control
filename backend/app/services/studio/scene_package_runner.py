"""Scene package runner for chained FF/LF execution inside Paperclip."""

from __future__ import annotations

import copy
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.schemas.scene_packages import (
    SceneOutputKind,
    ScenePackage,
    SceneRunResult,
    SceneShotPackage,
    SceneShotRun,
)


class ScenePackageRunnerError(RuntimeError):
    """Raised when a scene package cannot be executed."""


class ComfyClientProtocol(Protocol):
    async def upload_image(self, image_path: str) -> str: ...

    async def queue_prompt(self, workflow_api_json: dict[str, Any]) -> str: ...

    async def monitor_progress(self, prompt_id: str): ...

    async def get_history(self, prompt_id: str) -> dict[str, Any]: ...

    async def download_view_asset(
        self,
        filename: str,
        subfolder: str = "",
        asset_type: str = "output",
    ) -> bytes: ...


@dataclass(frozen=True)
class SceneHistoryArtifact:
    filename: str
    subfolder: str
    asset_type: str
    output_kind: SceneOutputKind


class ScenePackageRunner:
    def __init__(self, client: ComfyClientProtocol) -> None:
        self._client = client

    async def run(
        self,
        scene_package: ScenePackage,
        base_output_dir: str | Path | None = None,
    ) -> SceneRunResult:
        output_dir = scene_package.resolve_output_dir(base_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        previous_terminal_frame: Path | None = None
        shot_runs: list[SceneShotRun] = []

        for index, shot in enumerate(scene_package.shots, start=1):
            workflow = copy.deepcopy(shot.workflow_api_json)
            first_frame_path = self._resolve_first_frame(shot, previous_terminal_frame)
            await self._patch_image_input(
                workflow,
                node_id=shot.first_frame_target.node_id,
                input_name=shot.first_frame_target.input_name,
                image_path=first_frame_path,
            )

            if shot.last_frame_target is not None:
                if not shot.last_frame_path:
                    raise ScenePackageRunnerError(
                        f"Shot {shot.id} requires last_frame_path for "
                        f"{shot.last_frame_target.node_id}.{shot.last_frame_target.input_name}"
                    )
                await self._patch_image_input(
                    workflow,
                    node_id=shot.last_frame_target.node_id,
                    input_name=shot.last_frame_target.input_name,
                    image_path=Path(shot.last_frame_path),
                )

            prompt_id = await self._client.queue_prompt(workflow)
            async for _ in self._client.monitor_progress(prompt_id):
                pass
            history = await self._client.get_history(prompt_id)
            artifact = self._select_output_artifact(shot, history)
            output_path = output_dir / self._build_output_name(index, shot, artifact.filename)
            output_bytes = await self._client.download_view_asset(
                artifact.filename,
                artifact.subfolder,
                artifact.asset_type,
            )
            output_path.write_bytes(output_bytes)

            terminal_frame_path: Path | None = None
            if artifact.output_kind == SceneOutputKind.VIDEO:
                terminal_frame_path = output_dir / f"{shot.id}_last_frame.png"
                extract_terminal_frame(output_path, terminal_frame_path)
                previous_terminal_frame = terminal_frame_path
            else:
                previous_terminal_frame = output_path

            shot_runs.append(
                SceneShotRun(
                    shot_id=shot.id,
                    prompt_id=prompt_id,
                    output_path=str(output_path),
                    terminal_frame_path=str(terminal_frame_path) if terminal_frame_path else None,
                    history=history,
                )
            )

        return SceneRunResult(
            scene_id=scene_package.id,
            output_dir=str(output_dir),
            shots=shot_runs,
        )

    def _resolve_first_frame(
        self,
        shot: SceneShotPackage,
        previous_terminal_frame: Path | None,
    ) -> Path:
        if shot.chain_previous_terminal_frame:
            if previous_terminal_frame is None:
                raise ScenePackageRunnerError(
                    f"Shot {shot.id} is configured to chain from the previous shot, "
                    "but no prior terminal frame exists."
                )
            return previous_terminal_frame
        if not shot.first_frame_path:
            raise ScenePackageRunnerError(f"Shot {shot.id} is missing first_frame_path")
        return Path(shot.first_frame_path)

    async def _patch_image_input(
        self,
        workflow: dict[str, Any],
        *,
        node_id: str,
        input_name: str,
        image_path: Path,
    ) -> None:
        if node_id not in workflow:
            raise ScenePackageRunnerError(f"Workflow node {node_id} not found")
        uploaded_name = await self._client.upload_image(str(image_path))
        workflow[node_id].setdefault("inputs", {})[input_name] = uploaded_name

    def _select_output_artifact(
        self,
        shot: SceneShotPackage,
        history: dict[str, Any],
    ) -> SceneHistoryArtifact:
        outputs = history.get("outputs", {})
        if shot.output_node_id:
            outputs = {shot.output_node_id: outputs.get(shot.output_node_id, {})}

        output_keys = ("videos", "gifs") if shot.output_kind == SceneOutputKind.VIDEO else ("images",)
        for node_output in outputs.values():
            for key in output_keys:
                for item in node_output.get(key, []):
                    return SceneHistoryArtifact(
                        filename=item["filename"],
                        subfolder=item.get("subfolder", ""),
                        asset_type=item.get("type", "output"),
                        output_kind=shot.output_kind,
                    )
        raise ScenePackageRunnerError(
            f"No {shot.output_kind.value} output artifact found for shot {shot.id}"
        )

    def _build_output_name(self, index: int, shot: SceneShotPackage, original_name: str) -> str:
        suffix = Path(original_name).suffix or (
            ".mp4" if shot.output_kind == SceneOutputKind.VIDEO else ".png"
        )
        return f"{index:02d}_{shot.id}{suffix}"


def extract_terminal_frame(video_path: str | Path, output_path: str | Path) -> Path:
    source = Path(video_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    last_frame_index = max(_probe_total_frames(source) - 1, 0)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        f"select=eq(n\\,{last_frame_index})",
        "-vframes",
        "1",
        str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise ScenePackageRunnerError(f"ffmpeg failed extracting terminal frame: {result.stderr}")
    return target


def _probe_total_frames(video_path: Path) -> int:
    for extra_args in (
        ["-count_packets", "-show_entries", "stream=nb_read_packets"],
        ["-count_frames", "-show_entries", "stream=nb_read_frames"],
        ["-show_entries", "stream=nb_frames"],
    ):
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            *extra_args,
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            continue
        value = result.stdout.strip()
        if value.isdigit():
            return int(value)
    raise ScenePackageRunnerError(f"Could not determine total frames for {video_path}")
