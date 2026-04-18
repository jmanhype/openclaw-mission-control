"""Minimal ComfyUI client for Paperclip studio execution."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import websockets

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComfyProgressUpdate:
    percent: float | None
    node_id: str | None = None
    status: str | None = None
    current_step: str | None = None


class ComfyUIClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8188,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if host.startswith(("http://", "https://")):
            base_url = host
        else:
            base_url = f"http://{host}:{port}"
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            transport=transport,
        )
        self._client_id = str(uuid.uuid4())

    async def __aenter__(self) -> "ComfyUIClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def queue_prompt(self, workflow_api_json: dict[str, Any]) -> str:
        response = await self._client.post(
            "/prompt",
            json={"prompt": workflow_api_json, "client_id": self._client_id},
        )
        response.raise_for_status()
        payload = response.json()
        node_errors = payload.get("node_errors")
        if node_errors:
            raise RuntimeError(f"ComfyUI node errors: {node_errors}")
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return a prompt_id")
        return str(prompt_id)

    async def monitor_progress(self, prompt_id: str) -> AsyncIterator[ComfyProgressUpdate]:
        async for message_type, message_data in self._stream_progress(prompt_id):
            if message_type == "executing" and message_data.get("node") is None:
                return
            update = self._progress_update(message_type, message_data)
            if update is not None:
                yield update

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        response = await self._client.get(f"/history/{prompt_id}")
        response.raise_for_status()
        return response.json().get(prompt_id, {})

    async def upload_image(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        files = {"image": (path.name, path.read_bytes(), "image/png")}
        response = await self._client.post(
            "/upload/image",
            files=files,
            data={"overwrite": "true", "type": "input", "subfolder": "paperclip"},
        )
        response.raise_for_status()
        payload = response.json()
        name = payload.get("name")
        subfolder = payload.get("subfolder")
        if subfolder:
            return f"{subfolder}/{name}"
        return str(name)

    async def download_view_asset(
        self,
        filename: str,
        subfolder: str = "",
        asset_type: str = "output",
    ) -> bytes:
        response = await self._client.get(
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": asset_type},
        )
        response.raise_for_status()
        return response.content

    async def _stream_progress(
        self,
        prompt_id: str,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        ws_url = self._ws_url()
        async with websockets.connect(f"{ws_url}?clientId={self._client_id}") as socket:
            async for raw_message in socket:
                if isinstance(raw_message, bytes):
                    try:
                        raw_message = raw_message.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                if not raw_message.strip():
                    continue
                try:
                    payload = httpx.Response(200, text=raw_message).json()
                except ValueError:
                    continue
                message_type = payload.get("type")
                message_data = payload.get("data", {})
                if message_data.get("prompt_id") != prompt_id:
                    continue
                if message_type is None:
                    continue
                yield message_type, message_data

    def _progress_update(
        self,
        message_type: str,
        message_data: dict[str, Any],
    ) -> ComfyProgressUpdate | None:
        if message_type == "progress":
            value = message_data.get("value")
            max_value = message_data.get("max")
            if value is None or max_value in (None, 0):
                return None
            return ComfyProgressUpdate(
                percent=(float(value) / float(max_value)) * 100,
                current_step=f"{value}/{max_value}",
                node_id=_maybe_string(message_data.get("node")),
            )
        if message_type == "executing":
            node_id = message_data.get("node")
            if node_id is None:
                return None
            return ComfyProgressUpdate(percent=None, node_id=str(node_id), status="executing")
        if message_type == "execution_error":
            raise RuntimeError(
                "ComfyUI execution error at node "
                f"{_maybe_string(message_data.get('node_id'))}: "
                f"{message_data.get('exception_message', 'unknown error')}"
            )
        return None

    def _ws_url(self) -> str:
        if self._base_url.startswith("https://"):
            return self._base_url.replace("https://", "wss://", 1) + "/ws"
        return self._base_url.replace("http://", "ws://", 1) + "/ws"


def _maybe_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
