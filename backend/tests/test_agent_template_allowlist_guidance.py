# ruff: noqa: S101
from __future__ import annotations

from uuid import uuid4

import app.services.openclaw.provisioning as agent_provisioning
from tests.test_agent_provisioning_utils import _AgentStub, _GatewayStub


def test_lead_templates_include_allowlist_guidance_and_avoid_shell_line_continuations() -> None:
    gateway = _GatewayStub(
        id=uuid4(),
        name="Gateway",
        url="ws://gateway.example/ws",
        token=None,
        workspace_root="/tmp/openclaw",
    )
    board = type(
        "BoardStub",
        (),
        {
            "id": uuid4(),
            "name": "ComfyUI video pipeline",
            "board_type": "goal",
            "objective": "Run reusable video workflows",
            "success_metrics": {},
            "target_date": None,
            "goal_confirmed": True,
            "require_approval_for_done": True,
            "require_review_before_done": False,
            "comment_required_for_review": False,
            "block_status_changes_with_pending_approval": False,
            "only_lead_can_change_status": False,
            "max_agents": 1,
        },
    )()
    agent = _AgentStub(
        name="Comfy Video Lead",
        is_board_lead=True,
        openclaw_session_id="agent:lead-bfedc5b2-5f0a-42d2-81d5-69bb33ca82b4:main",
    )
    context = agent_provisioning._build_context(
        agent=agent,
        board=board,
        gateway=gateway,
        auth_token="secret-token",
        user=None,
    )

    rendered = agent_provisioning._render_agent_files(
        context,
        agent,
        {"TOOLS.md", "HEARTBEAT.md", "BOOTSTRAP.md"},
        include_bootstrap=True,
        template_overrides=dict(agent_provisioning.BOARD_SHARED_TEMPLATE_MAP),
    )

    assert "Do not use shell line continuations (`\\` + newline)" in rendered["TOOLS.md"]
    assert "Do not use shell line continuations (`\\` + newline)" in rendered["HEARTBEAT.md"]
    assert "\\\n" not in rendered["HEARTBEAT.md"]
    assert "\\\n" not in rendered["BOOTSTRAP.md"]
