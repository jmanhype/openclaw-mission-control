# ruff: noqa: INP001
"""Queue worker registration tests for lifecycle reconcile tasks."""

from __future__ import annotations

import pytest

import app.services.queue_worker as queue_worker
from app.services.openclaw.lifecycle_queue import TASK_TYPE as LIFECYCLE_TASK_TYPE
from app.services.queue_worker import _TASK_HANDLERS


def test_worker_registers_lifecycle_reconcile_handler() -> None:
    assert LIFECYCLE_TASK_TYPE in _TASK_HANDLERS


@pytest.mark.asyncio
async def test_periodic_assigned_agent_rescue_runs_when_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, int] = {}

    async def _fake_rescue(*, limit: int | None = None) -> int:
        captured["limit"] = limit or -1
        return 2

    monkeypatch.setattr(queue_worker, "rescue_stranded_assigned_agents", _fake_rescue)
    monkeypatch.setattr(queue_worker.settings, "assigned_agent_rescue_sweep_seconds", 30.0)
    monkeypatch.setattr(queue_worker.settings, "assigned_agent_rescue_batch_size", 4)
    moments = iter((100.0, 130.0))
    monkeypatch.setattr(queue_worker, "_monotonic", lambda: next(moments))

    next_run_at = await queue_worker._run_periodic_assigned_agent_rescue(next_run_at=0.0)

    assert captured == {"limit": 4}
    assert next_run_at == 160.0
