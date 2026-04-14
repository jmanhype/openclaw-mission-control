from __future__ import annotations

from uuid import uuid4

from app.models.agents import Agent
from app.services.openclaw.db_agent_state import mark_provision_complete, resolve_heartbeat_config
from app.services.openclaw.provisioning_db import AgentLifecycleService


def test_mark_provision_complete_sets_last_seen_for_online_agent() -> None:
    agent = Agent(name="Riley Gateway Agent", gateway_id=uuid4())

    mark_provision_complete(agent, status="online")

    assert agent.status == "online"
    assert agent.provision_requested_at is None
    assert agent.provision_action is None
    assert agent.last_seen_at is not None
    assert AgentLifecycleService.with_computed_status(agent).status == "online"


def test_mark_provision_complete_leaves_last_seen_empty_for_non_online_status() -> None:
    agent = Agent(name="Riley Gateway Agent", gateway_id=uuid4())

    mark_provision_complete(agent, status="offline")

    assert agent.status == "offline"
    assert agent.last_seen_at is None


def test_resolve_heartbeat_config_keeps_board_scoped_agents_internal() -> None:
    heartbeat = resolve_heartbeat_config(
        board_id=uuid4(),
        is_board_lead=True,
        raw={"every": "10m", "target": "last", "includeReasoning": False},
    )

    assert heartbeat["target"] == "none"


def test_resolve_heartbeat_config_preserves_explicit_real_channel_targets() -> None:
    heartbeat = resolve_heartbeat_config(
        board_id=uuid4(),
        is_board_lead=True,
        raw={"every": "10m", "target": "telegram", "includeReasoning": False},
    )

    assert heartbeat["target"] == "telegram"
