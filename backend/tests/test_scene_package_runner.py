from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.scene_packages import (
    SceneOutputKind,
    ScenePackage,
    SceneShotPackage,
    SceneWorkflowInputTarget,
)
from app.services.studio.scene_package_runner import (
    ScenePackageRunner,
    ScenePackageRunnerError,
)


class StubClient:
    def __init__(self) -> None:
        self.uploaded_paths: list[str] = []
        self.prompt_counter = 0
        self.queued_workflows: list[dict] = []

    async def upload_image(self, image_path: str) -> str:
        self.uploaded_paths.append(image_path)
        return f"paperclip/{Path(image_path).name}"

    async def queue_prompt(self, workflow_api_json: dict) -> str:
        self.prompt_counter += 1
        self.queued_workflows.append(workflow_api_json)
        return f"prompt-{self.prompt_counter}"

    async def monitor_progress(self, prompt_id: str):
        if False:
            yield prompt_id

    async def get_history(self, prompt_id: str) -> dict:
        return {
            "outputs": {
                "save_video": {
                    "gifs": [
                        {
                            "filename": f"{prompt_id}.mp4",
                            "subfolder": "scene",
                            "type": "output",
                        }
                    ]
                }
            }
        }

    async def download_view_asset(self, filename: str, subfolder: str, asset_type: str) -> bytes:
        return b"fake-video"


@pytest.mark.anyio
async def test_scene_package_runner_uses_previous_terminal_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extracted_calls: list[tuple[Path, Path]] = []

    def fake_extract_terminal_frame(video_path: Path, output_path: Path) -> Path:
        output_path.write_bytes(b"png")
        extracted_calls.append((video_path, output_path))
        return output_path

    monkeypatch.setattr(
        "app.services.studio.scene_package_runner.extract_terminal_frame",
        fake_extract_terminal_frame,
    )

    first_frame = tmp_path / "first.png"
    last_frame = tmp_path / "last.png"
    first_frame.write_bytes(b"first")
    last_frame.write_bytes(b"last")

    workflow = {
        "10": {"class_type": "LoadImage", "inputs": {"image": ""}},
        "11": {"class_type": "LoadImage", "inputs": {"image": ""}},
    }
    scene_package = ScenePackage(
        id="scene_001",
        title="Test",
        output_dir="renders",
        shots=[
            SceneShotPackage(
                id="shot_001",
                workflow_api_json=workflow,
                first_frame_path=str(first_frame),
                last_frame_path=str(last_frame),
                first_frame_target=SceneWorkflowInputTarget(node_id="10", input_name="image"),
                last_frame_target=SceneWorkflowInputTarget(node_id="11", input_name="image"),
                output_kind=SceneOutputKind.VIDEO,
            ),
            SceneShotPackage(
                id="shot_002",
                workflow_api_json=workflow,
                first_frame_target=SceneWorkflowInputTarget(node_id="10", input_name="image"),
                chain_previous_terminal_frame=True,
                output_kind=SceneOutputKind.VIDEO,
            ),
        ],
    )

    client = StubClient()
    runner = ScenePackageRunner(client)
    result = await runner.run(scene_package, base_output_dir=tmp_path)

    assert len(result.shots) == 2
    assert client.uploaded_paths[0] == str(first_frame)
    assert client.uploaded_paths[1] == str(last_frame)
    assert client.uploaded_paths[2].endswith("shot_001_last_frame.png")
    assert extracted_calls[0][1].name == "shot_001_last_frame.png"
    assert extracted_calls[1][1].name == "shot_002_last_frame.png"


@pytest.mark.anyio
async def test_scene_package_runner_requires_previous_terminal_frame_for_chained_shot(
    tmp_path: Path,
) -> None:
    scene_package = ScenePackage(
        id="scene_001",
        title="Test",
        output_dir="renders",
        shots=[
            SceneShotPackage(
                id="shot_001",
                workflow_api_json={"10": {"class_type": "LoadImage", "inputs": {"image": ""}}},
                first_frame_target=SceneWorkflowInputTarget(node_id="10", input_name="image"),
                chain_previous_terminal_frame=True,
            )
        ],
    )

    runner = ScenePackageRunner(StubClient())
    with pytest.raises(ScenePackageRunnerError):
        await runner.run(scene_package, base_output_dir=tmp_path)


def test_scene_package_from_path_loads_json(tmp_path: Path) -> None:
    scene_file = tmp_path / "scene.json"
    scene_file.write_text(
        """
{
  "id": "scene_001",
  "title": "Test Scene",
  "output_dir": "renders",
  "shots": [
    {
      "id": "shot_001",
      "workflow_api_json": {
        "10": {
          "class_type": "LoadImage",
          "inputs": {
            "image": ""
          }
        }
      },
      "first_frame_path": "/tmp/first.png",
      "first_frame_target": {
        "node_id": "10",
        "input_name": "image"
      },
      "output_kind": "video"
    }
  ]
}
""",
        encoding="utf-8",
    )

    scene_package = ScenePackage.from_path(scene_file)

    assert scene_package.id == "scene_001"
    assert scene_package.shots[0].output_kind == SceneOutputKind.VIDEO
