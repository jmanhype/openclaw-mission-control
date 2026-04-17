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
        {"AGENTS.md", "TOOLS.md", "HEARTBEAT.md", "BOOTSTRAP.md"},
        include_bootstrap=True,
        template_overrides=dict(agent_provisioning.BOARD_SHARED_TEMPLATE_MAP),
    )

    assert "Do not use shell line continuations (`\\` + newline)" in rendered["TOOLS.md"]
    assert "Do not use shell line continuations (`\\` + newline)" in rendered["HEARTBEAT.md"]
    assert "/api/v1/agent/boards/" in rendered["TOOLS.md"]
    assert '"message":"' in rendered["TOOLS.md"]
    assert '"assigned_agent_id":null' in rendered["TOOLS.md"]
    assert "Never assign a task to yourself when you are the board lead" in rendered["TOOLS.md"]
    assert "External target failures (`4xx`, `5xx`, auth, allowlist/exec denial, provider `429`, missing dependency) are blocker evidence and must be reported in the same cycle." in rendered["HEARTBEAT.md"]
    assert "If task-comment write fails, post the same blocker in board chat and say the task-comment endpoint failed." in rendered["HEARTBEAT.md"]
    assert "For remote execution claims (`submitted`, `running`, `continuing`, `in progress`, `unblocked`), include fresh execution evidence from the target system in the same cycle: prompt/job/build id plus exact output path." in rendered["HEARTBEAT.md"]
    assert "After approval or unblock, the next execution update must be either a fresh execution id from the target system or an exact blocker. Status-only continuation claims are invalid." in rendered["HEARTBEAT.md"]
    assert "Artifact existence is not proof of success." in rendered["HEARTBEAT.md"]
    assert "Before moving to `review`, post both proof of execution and proof of quality." in rendered["HEARTBEAT.md"]
    assert "For first-frame/last-frame or chained-segment workflows, record exact first/last keyframe paths for each segment" in rendered["HEARTBEAT.md"]
    assert "If execution, delegation, or tooling fails, publish the blocker immediately with exact failing system, error, and smallest next step." in rendered["AGENTS.md"]
    assert "Do not silently retry the same failing path more than once without posting blocker evidence." in rendered["AGENTS.md"]
    assert "If you say remote work is `submitted`, `running`, `continuing`, or `unblocked`, include a fresh target-system execution id and exact output path in that same update." in rendered["AGENTS.md"]
    assert "After human approval/unblock, your next remote-execution update must be either a new execution id or an exact blocker, never status-only continuation language." in rendered["AGENTS.md"]
    assert "For multi-step media, scene, or other staged tasks, maintain one reusable scene/run package" in rendered["AGENTS.md"]
    assert "For remote workflow/render/build tasks, keep exactly one canonical runnable artifact for the next attempt" in rendered["AGENTS.md"]
    assert "If multiple local variants exist (`*_fixed`, `*_api`, `*_workflow`, copied templates, converted exports), explicitly mark one canonical path and treat the others as stale until replaced." in rendered["AGENTS.md"]
    assert "Artifact existence, prompt submission, or successful encode is not enough to claim success." in rendered["AGENTS.md"]
    assert "Local workflow edits or converted files are not proof that remote execution started." in rendered["AGENTS.md"]
    assert "### Package / Artifact Set" in rendered["AGENTS.md"]
    assert "### Quality Gate" in rendered["AGENTS.md"]
    assert "For remote workflow/render/build tasks, name one canonical runnable artifact path" in rendered["HEARTBEAT.md"]
    assert "Local workflow/package edits are not proof that a rerun started." in rendered["HEARTBEAT.md"]
    assert "\\\n" not in rendered["HEARTBEAT.md"]
    assert "\\\n" not in rendered["BOOTSTRAP.md"]
